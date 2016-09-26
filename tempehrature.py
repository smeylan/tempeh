import RPi.GPIO as GPIO
import subprocess, re, sys, time, os, pdb, pickle
GPIO.setmode(GPIO.BCM)
os.chdir('/home/pi/projects/tempehrature')
import PID


st = {0:'OFF',1:'ON'}

class Oven(object):
	def __init__(self, thermPin, lightPin, updateInterval=300):
		print('Initializing oven')
		print('light pin: '+str(lightPin))
		print('thermometer pin: '+str(thermPin))
		self.light = Light(lightPin)		
		self.thermometer = Thermometer(thermPin)		
		self.pid = PID.PID()	
		self.updateInterval = updateInterval
		
		self.temp = 0
		self.humidity = 0
		self.desired_temp = 0
		self.baking = False

		#record the temperature and the state of the oven
		self.tempLog = Log(['time','temp','humidity'])
		self.stateLog = Log(['time','state'])
		self.setState(0)
		self.getTempHumidity()


	def setState(self, state):
		'''turn the light on or off'''
		self.light.setState(state)
		self.stateLog.log['time'].append(time.time())
		self.stateLog.log['state'].append(state)
		self.stateLog.save('stateLog.pickle')
		print('Oven turned '+st[state])

	def bake(self, temp):
		'''PID-controlled duty cycle'''
		self.baking = True			
		self.updateInterval = self.updateInterval
		print('PID-controlled Baking, updating every '+str(self.updateInterval)+' seconds')
		self.desired_temp = temp
		self.pid.SetPoint = self.desired_temp
		self.pid.setSampleTime(self.updateInterval)
				
		while self.baking:
			#!!! see 'deadband'
			#this needs to be threaded in some way so that it can be killed
			self.getTempHumidity(previousReadings=self.tempLog.log['temp'][-5:])
			self.pid.update(self.temp)
			output = self.pid.output
			print('Output: '+str(output))
			highPass = 1.0
			proportionOn = min(max(0.,output), highPass)	
			print('Current duty load: '+str(proportionOn))	

			if proportionOn <= .1:
				print('Duty proportion < .1, keeping off...')
				if self.light.state == 1:
					self.setState(0)
				
				self.stateLog.log['time'].append(time.time())
				self.stateLog.log['state'].append(self.light.state)
				self.stateLog.save('stateLog.pickle')	
				
				time.sleep(self.updateInterval)	
			elif proportionOn > .1 and proportionOn < .9:
				print('Normal duty proportion, mixing...')
				self.setState(1)	
			 	time.sleep(proportionOn * self.updateInterval)
				self.setState(0)
				time.sleep((1 - proportionOn) * self.updateInterval)	
			elif proportionOn > .9:
				print('Duty proportion > .9, keeping on...')
				if self.light.state == 0:
					self.setState(1)

				self.stateLog.log['time'].append(time.time())
				self.stateLog.log['state'].append(self.light.state)
				self.stateLog.save('stateLog.pickle')	
								
				time.sleep(self.updateInterval)			

	def stopBaking(self):
		self.baking = False

	def getTempHumidity(self, previousReadings=None):
		'''get temperature and humidity and log all values'''
		# filter new thermometer readings by the moving average of previous readings
		if not previousReadings or previousReadings is None: 		
			self.temp, self.humidity  = self.thermometer.read()					
		else:	
			validReading = False		
			tolerance = 30
			failsafe_threshold = 5
			tries = 0
			while not validReading:			
				self.temp, self.humidity  = self.thermometer.read()	
				mean = reduce(lambda x, y: x + y, previousReadings) / len(previousReadings)			
				if (mean - tolerance ) < self.temp < (mean + tolerance):
					validReading = True
				else:	
					tries += 1
					if tries > failsafe_threshold:
						self.setState(0)
						raise ValueError('Too many out-of-range thermomter readings')
			
		self.tempLog.log['time'].append(time.time())
		self.tempLog.log['temp'].append(self.temp)		
		self.tempLog.log['humidity'].append(self.humidity)		
		self.tempLog.save('tempLog.pickle')


class Thermometer(object):
	def __init__(self, pinNumber):
		self.pinNumber = pinNumber
		
	def read(self):
		while(True):	
			output = subprocess.check_output(["./Adafruit_DHT", "22", str(self.pinNumber)]);	  
			matches = re.search("Temp =\s+([0-9.]+)", output)
			if (not matches):
				print('Thermometer checksum error, waiting for new reading....')
				time.sleep(3) 
				continue
			else:	
				temp = float(matches.group(1))

			# search for humidity printout
			matches = re.search("Hum =\s+([0-9.]+)", output)
			if (not matches):
				time.sleep(3)
				continue
			else:
				humidity = float(matches.group(1))

			#print "Temperature: %.1f C" % temp
			temp_f = temp*(9./5.) + 32
			print "Temperature %.1f F" % temp_f
			print "Humidity:    %.1f %%" % humidity
			return((temp_f, humidity))


class Light(object):
	def __init__(self, pinNumber):
		GPIO.setup(pinNumber, GPIO.OUT)		
		self.pinNumber = pinNumber
		self.state = 0
	def setState(self, state):		
		self.state = state
		GPIO.output(self.pinNumber, state)
		print('Light turned '+st[state])		

class Log(object):
	def __init__(self, fields):
		self.log = {}
		for field in fields:
			self.addChannel(field)
	def addChannel(self,name):	
		self.log[name] = []
	def save(self,fname):
		pickle.dump(self, open( fname, "wb" ))	

#interaction should just be with the oven
oven = Oven(thermPin=4,lightPin=23, updateInterval=300)		
oven.bake(105) #90.2 produces 87.3; 92 produces 89.2
#oven.setState(1)
#oven.setState(0)
#oven.getTempHumidity()
