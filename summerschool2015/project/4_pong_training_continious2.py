import nest
import nest.raster_plot as rplt
import numpy as np
import matplotlib.pyplot as plt
import pong_environment_training_continious2 as env
from mpl_toolkits.mplot3d import Axes3D
import os
import json
import math

def SaveNetworkToFile(filename, source, target):
	if os.path.exists(filename):
		os.remove(filename)
	status = nest.GetStatus(nest.GetConnections(source, target))
	status = [{'source': i['source'], 'target': i['target'], 'weight': i['weight'], 'delay': i['delay'], 'synapse_model': "static_synapse"} for i in status] 
	f = open(filename, 'w+')
	f.write(json.dumps(status))
	f.close()

NUM_ITERATIONS = 200
LEARNING_RATE = 0.005
wta_ex_weights = 10.5
wta_inh_weights = -2.6
wta_ex_inh_weights = 2.8
noise_weights = 2.15

nest.ResetKernel()
nest.set_verbosity("M_FATAL")

rank = nest.Rank()
size = nest.NumProcesses() 
seed = np.random.randint(0, 1000000)
num_threads = 4
nest.SetKernelStatus({"local_num_threads": num_threads})
nest.SetKernelStatus({"rng_seeds": range(seed+num_threads * size + 1, seed + 2 * (num_threads * size) + 1),
        		      "grng_seed": seed+size+num_threads,
                      "resolution": 0.1})

# Create left right sensors
diff_K = 100. # specify K between diff and generator rate
diff_K2 = 20000.
sensors = {'left':nest.Create('poisson_generator')[0], 'right':nest.Create('poisson_generator')[0] }

# Create diff neurons
density = 0.3 # neurons for one pixel
diffNeuronsPositions = []
diffNeurons = []
for i in range(env.params['screenSize']):
    if(np.random.rand() < density):
        neuron = nest.Create('iaf_psc_alpha')[0]
        diffNeurons.append(neuron)
        diffNeuronsPositions.append({'position':i, 'neuron':neuron})

# connect left-right 
m = 20.
length = env.params['screenSize']
p1 = length / 2
k1 = m/p1
for i in range(len(diffNeuronsPositions)):
    neuronPosition = diffNeuronsPositions[i]
    x = neuronPosition['position']
    #connect neuron to the difference sensor depends on it position
    if(x >= 0 and x <= p1):
        nest.Connect(sensors['left'], neuronPosition['neuron'], {"weight":x*k1})
    if(x >= p1 and x <= length):
        nest.Connect(sensors['right'], neuronPosition['neuron'], {"weight":-(x * k1) + m*2})

#create actions
numActions = len(env.actionsAvailable)
actions = []
for i in range(numActions):
    actions.append(nest.Create('iaf_psc_alpha', 30))
    nest.Connect(diffNeurons, actions[i], 'all_to_all', {'weight': 0.1})
all_actions = np.ravel(actions).tolist()
nest.Connect(diffNeurons, actions[0], 'all_to_all', {'weight': 0.1})
nest.Connect(diffNeurons, actions[1], 'all_to_all', {'weight': -0.5})
nest.Connect(diffNeurons, actions[2], 'all_to_all', {'weight': 0.1})
 
# create noise
noise = nest.Create('poisson_generator', 10, {'rate': 3000.})
nest.Connect(noise, actions[0], 'all_to_all', {'weight': noise_weights})
nest.Connect(noise, actions[2], 'all_to_all', {'weight': noise_weights})
nest.Connect(noise, actions[1], 'all_to_all', {'weight': 1.1*noise_weights})


sd_all = nest.Create('spike_detector')
nest.Connect(diffNeurons, sd_all)

sd_actions = nest.Create('spike_detector', numActions)
for i in range(numActions):
    nest.Connect(actions[i], [sd_actions[i]], 'all_to_all')
sd_all_actions = nest.Create('spike_detector')
nest.Connect(all_actions, sd_all_actions, 'all_to_all')

# Main loop
actions_executed = 0
last_action_time = 0
in_end_position = False
env.init_new_trial()
outcomes = []
time = []
totalOutcome = 0

while actions_executed < NUM_ITERATIONS:
    if not in_end_position:
        state = env.getState().copy()
        print 'difference: ', state['diff']

        if(state['diff'] >= 0):
            nest.SetStatus([sensors['right']], {'rate':diff_K*state['diff']})
        else:
            nest.SetStatus([sensors['left']], {'rate':-diff_K*state['diff']})
        nest.SetStatus(noise, {'rate': 3000. })
        
        nest.Simulate(100)
        max_rate = -1
        chosen_action = -1
        for i in range(len(sd_actions)):
            rate = len([e for e in nest.GetStatus([sd_actions[i]], keys='events')[0]['times'] if e > last_action_time])
            if rate > max_rate:
                max_rate = rate # the population with the hightes rate wins
                chosen_action = i

        possible_actions = env.actionsAvailable
        FIRE_RATE_K = 0.5
        new_position, outcome, in_end_position = env.move(possible_actions[chosen_action], max_rate*FIRE_RATE_K)

        print "iteration:", actions_executed, "action:", chosen_action, 
        print "new pos:", new_position, "reward:", outcome
        
        # increase a weight of fired sensor neurons
        events = nest.GetStatus(sd_all, keys='events')[0]
        senders = [ j for (i,j) in zip(events['times'],events['senders']) if i > last_action_time ]
        if(len(senders) > 0):
            #rplt.from_device(sd_all_actions, title="Actions")
            #rplt.from_device(sd_all, title="Difference neurons")
            #rplt.show()
            if(chosen_action != 1):
                conn = nest.GetConnections(senders, actions[chosen_action])
                ww = nest.GetStatus(conn, keys='weight')[0]
                ww += outcome*LEARNING_RATE
                nest.SetStatus(conn, {'weight':ww})                           
            else:
                conn = nest.GetConnections(noise, actions[chosen_action])
                ww = nest.GetStatus(conn, keys='weight')[0]
                ww += outcome*LEARNING_RATE
                nest.SetStatus(conn, {'weight':ww})                
            
        # stimulate new state 
        nest.SetStatus([sensors['right']], {'rate':0.})
        nest.SetStatus([sensors['left']], {'rate':0.})
        nest.SetStatus(noise, {'rate': 0. })

        nest.Simulate(50.)
        
        time.append(last_action_time)
        totalOutcome += outcome
        outcomes.append(totalOutcome)
        last_action_time += 150
        actions_executed += 1
    else:
        position = env.getState().copy()        
        _, in_end_position = env.init_new_trial()
        nest.SetStatus([sensors['right']], {'rate':0.})
        nest.SetStatus([sensors['left']], {'rate':0.})
        nest.SetStatus(noise, {'rate': 0. })

SaveNetworkToFile("connections.dat", diffNeurons, all_actions)
plt.plot(time, outcomes)
plt.show()
rplt.from_device(sd_all_actions, title="Actions")
rplt.from_device(sd_all, title="Difference neurons")
rplt.show()


