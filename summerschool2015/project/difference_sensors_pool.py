import matplotlib.pyplot as plt
import numpy as np
import math

m = 10.
length = 480
p1 = length/3.
p2 = p1*2.
k1 = m/p2
k2 = 0.02*m

def leftSensor(x):
    if(x >= 0 and x <= p1):
        return x * k1
    elif(x > p1 and x <=p2):
        return k2*math.sqrt(-x + 320.)
    else:
        return 0

def rightSensor(x):
    if(x >= p2 and x <= length):
        return -(x * k1) + m*3./2.
    elif(x > p1 and x <=p2):
        return k2*math.sqrt(x + 160.)
    else:
        return 0

x = np.arange(0, length, 20)
s1 = np.vectorize(leftSensor)
s2 = np.vectorize(rightSensor)

y1 = s1(x)
y2 = s2(x)
y3 = y1 + y2

plt.plot(x, y1, 'b-', x, y2, 'g-', x, y3, 'r-')
plt.show()
