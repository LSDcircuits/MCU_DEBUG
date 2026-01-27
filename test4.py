import threading
import time


# All data reads and writes here as instance 
# so we treat this as a struct or just memory which does nothing
# unless a functions declares the value through state
class SystemState:

    # __init__ sets up internal variables 
    # initalizationfuncrtion for each instance
    # self.[] is saying create a object in this class 

    def __init__(self):
        self.lock = threading.Lock() # <-- Mutex    
     

        self.value_A = 0  # <-- data stored here 
        self.value_B = 0  # <-- and here 

        self.running = True # <-- control flag, so threads can run given this val is tru
        # but can be used as a global on off swithc



# data A is updated here 
class SensorA(threading.Thread): # <-- sensor a is a thread class
    def __init__(self, state): # <- we initiate this class (self) and initiate SystemState through state
        super().__init__(daemon=True) # <-- super declares parent class (REQUIRED)
        # WHAT IT MEANS: (Run the initialization code of the Thread class)
        
        # - thread ID
        # - execution target
        # - daemon flag
        # - OS resources    


        self.state = state # define state in this class

    def run(self): 
        while self.state.running: # <- this holds true from (class SystemState:)
            time.sleep(0.2)  # fast rate
            with self.state.lock: 
                self.state.value_A += 1

            # Thread A enters lock
            # Thread A updates to 11
            # Thread A leaves

            # Thread B enters lock
            # Thread B updates to 12
            # Thread B leaves

            #Thread A touching shared memory
            #Thread B touching shared memory at same time
            #→ data collision without lock

            # another way to view it:

            # Monitor reads A = 10
            # SensorB updates B from 20 → 25
            # Monitor reads B = 25

            #A = 10
            #B = 25
            # this combination never existed but locking makes it do it in this order:
            # Thread A enters → updates A → leaves
            # Thread B enters → updates B → leaves
            # Monitor enters → reads A and B → leaves

            # now evey update is based on rthe same time frame!!! yippie

            # Ik its confusing but needed

# equivalent of Sensor A 
class SensorB(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state

    def run(self):
        while self.state.running:
            time.sleep(1.0)  # slow rate
            with self.state.lock:
                self.state.value_B += 5


class Monitor(threading.Thread):
    def __init__(self, state):
        super().__init__(daemon=True)
        self.state = state

    def run(self):
        while self.state.running:
            with self.state.lock:  # to read the values we must lock it again
                # same as in the A&B sensor reading but now instead we read from the class that holds the values 
                a = self.state.value_A
                b = self.state.value_B

            print(f"A: {a} | B: {b}")
            # yipieee, kind off 
            time.sleep(0.5)



state = SystemState() # <- now it makes sense rigth :)??
# shared object passed to threads. = Systemstate() out value class so to say
# so when we do:

# def __init__(self, state): (here we declare to initiate state)
#     super().__init__(daemon=True)
#     self.state = state

# this is + the class SystemState() is what gives us access through threads globally

SensorA(state).start() # <-- initiate A thread 
SensorB(state).start() # <-- initiate B thread
Monitor(state).start() # <-- initiate Monitor thread

# these 3 classes run fucntions as threads individually.
# 

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    state.running = False
    print("System stopped.")
