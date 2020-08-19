import subprocess, os, sys
import threading
from tabulate import tabulate
import signal
import time
from time import gmtime, strftime
import queue, sqlite3
jobs=[]
jobscnt=0
jobq=queue.Queue()
threadpoolmax=1

class trabajo:
    def __init__(self, cmd, pwd):
        self.cmd=cmd
        self.pwd=pwd
        self.stdout=b''
        self.stderr=b''
        self.thread=None
        self.status=0 #0: pending, 1: running, 2: finished
        self.statustext=["-","+","#","X"]
        self.proc=None
        self.createtime=strftime("%Y-%m-%d %H:%M:%S", gmtime())
        self.runtime=""
        self.finishtime=""
    def run(self):
        if self.status==0:
            self.runtime=strftime("%Y-%m-%d %H:%M:%S", gmtime())
            self.status+=1
            self.proc = subprocess.Popen(self.cmd, shell=True,
                stdout = subprocess.PIPE,stderr = subprocess.STDOUT, cwd=self.pwd)
            # self.stdout=self.proc.stdout
            # self.stderr=self.proc.stderr
            for line in self.proc.stdout:
                self.stdout+=line
            self.proc.wait()
            self.finishtime=strftime("%Y-%m-%d %H:%M:%S", gmtime())
            self.status+=1
    def showstdout(self):
        subprocess.run('vim -', shell=True, input=self.stdout)
    # def showstderr(self):
    #     subprocess.run('vim -', shell=True, input=self.stderr)
    def summary(self):
        return (self.statustext[self.status], self.cmd[:50], self.createtime, self.runtime, self.finishtime)
    def kill(self):
        if self.proc is not None:
            self.proc.kill()
        self.status=3

ctrlc_cnt=0
def signal_handler(sig, frame):
    global ctrlc_cnt
    if ctrlc_cnt==0:
        print('\nPress again to exit')
        sys.stdout.write('[%s] > '%os.getcwd())
        sys.stdout.flush()
        ctrlc_cnt+=1
    else:
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def poolrunner():
    print("start poolrunner")
    running_jobs=[]
    while True:
        if jobq.empty():
            time.sleep(1)
        while len(running_jobs)<threadpoolmax:
            q=jobq.get()
            qthread=threading.Thread(target=q.run())
            qthread.start()
            running_jobs.append(qthread)
            # print("run", q.summary())
        for t in running_jobs:
            if not t.is_alive():
                running_jobs.remove(t)
        time.sleep(1)


x = threading.Thread(target=poolrunner)
x.start()
while True:    
    sys.stdout.write('[%s] > '%os.getcwd())
    cmd=input()
    ctrlc_cnt=0
    if cmd[0:2]=='cd':
        try:
            os.chdir(os.path.join(os.getcwd(), cmd.split(' ')[1]))
        except: print("Cannot cd.")
    elif cmd[0]=='!':
        cmds=cmd.split(" ")
        if cmd=='!ls':
            print(tabulate([(idx,*i.summary()) for idx,i in enumerate(jobs)], tablefmt="pretty",
                headers=["ID","Status","Command","create","run","finished"]))
        elif cmds[0]=='!k':
            if len(cmds)==2 and cmds[1].isdigit():
                jobs[int(cmds[1])].kill()
        elif cmds[0]=='!s':
            if len(cmds)==2 and cmds[1].isdigit():
                jobs[int(cmds[1])].showstdout()
        # elif cmds[0]=='!showstderr':
        #     if len(cmds)==2 and cmds[1].isdigit():
        #         jobs[int(cmds[1])].showstderr()
        else:
            print("Job control command support these options:")
            print("\t!ls")
            print("\t!k <ID> kill")
            print("\t!s <ID> show stdout")
            # print("\t!showstderr <ID>")
    else:
        newjob=trabajo(cmd, os.getcwd())
        jobs.append(newjob)
        jobq.put(newjob)