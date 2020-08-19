import subprocess, os, sys
import threading
from tabulate import tabulate
import signal
import time
from time import gmtime, strftime
import queue, sqlite3
import readline
from io import StringIO

vimrc='''" :Less
" turn vim into a pager for psql aligned results 
fun! Less()
1
set nocompatible
set nowrap
set scrollopt=ver
set scrollbind

nmap ^[OC zL
nmap ^[OB ^E
nmap ^[OD zH
nmap ^[OA ^Y
nmap <Left> 20zh
nmap <Right> 20zl
nmap <Up> 20k
nmap <Down> 20j
nmap <Space> <PageDown>
" faster quit (I tend to forget about the upper panel)
nmap q :qa!<CR>
nmap Q :qa!<CR>
endfun
command! -nargs=0 Less call Less()
'''
with open('/tmp/.vimrc','w') as f:
    f.write(vimrc)

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

con=sqlite3.connect("log.db")
con.execute("create table if not exists jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, status text, cmd text, create_t text, run_t text, finish_t text)")
cur=con.execute('select max(id) from jobs')
jobs=cur.fetchall()
con.close()
if jobs[0][0] is None:
    jobscnt=0
else:
    jobscnt=jobs[0][0]
print("History jobs:", jobscnt)

jobs={}
jobq=queue.Queue()
threadpoolmax=2

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
            with sqlite3.connect('log.db') as con:
                con.execute('insert into jobs(status, cmd, create_t, run_t, finish_t) values(?,?,?,?,?)', 
                    self.summary())
    def showstdout(self):
        subprocess.run('vim -c "Less" -u /tmp/.vimrc -', shell=True, input=self.stdout)
    # def showstderr(self):
    #     subprocess.run('vim -', shell=True, input=self.stderr)
    def summary(self):
        return (self.statustext[self.status], self.cmd, self.createtime, self.runtime, self.finishtime)
    def shortsummary(self, maxlen=40):
        shortcmd="\n".join(chunks(self.cmd, maxlen))
        return (self.statustext[self.status], shortcmd, self.createtime, self.runtime, self.finishtime)
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
    global threadpoolmax
    # print("start poolrunner")
    running_jobs=[]
    while True:
        if not jobq.empty():
            # print(len(running_jobs), threadpoolmax)
            while len(running_jobs)<threadpoolmax:
                q=jobq.get()
                # print("1")
                qthread=threading.Thread(target=q.run)
                # print("2")
                qthread.start()
                # print("3")
                running_jobs.append(qthread)
                # print("4")
                # print("run", q.summary())
            for t in running_jobs:
                if not t.is_alive():
                    running_jobs.remove(t)
        time.sleep(0.2)


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
    elif cmd=='ls':
        print(subprocess.getoutput("ls"))
    elif len(cmd)>0 and cmd[0]=='!':
        cmds=cmd.split(" ")
        if cmd=='!ls':
            print(tabulate([(k,*jobs[k].shortsummary()) for k in jobs], tablefmt="pretty",
                headers=["ID","Status","Command","create","run","finished"]))
        elif cmds[0]=='!k':
            if len(cmds)==2 and cmds[1].isdigit():
                jobs[int(cmds[1])].kill()
        elif cmds[0]=='!s':
            if len(cmds)==2 and cmds[1].isdigit():
                jobs[int(cmds[1])].showstdout()
        elif cmds[0]=='!j':
            if len(cmds)==2 and cmds[1].isdigit():
                threadpoolmax=int(cmds[1])
            else:
                print("Thread pool size:", threadpoolmax)
        # elif cmds[0]=='!showstderr':
        #     if len(cmds)==2 and cmds[1].isdigit():
        #         jobs[int(cmds[1])].showstderr()
        else:
            print("Job control command support these options:")
            print("\t!ls")
            print("\t!k <ID> kill")
            print("\t!s <ID> show stdout")
            print("\t!j <NUM> modify max thread pool size")
            print("\t!j         show max thread pool size")
            # print("\t!showstderr <ID>")
    elif len(cmd)>0:
        newjob=trabajo(cmd, os.getcwd())
        jobscnt+=1
        jobs[jobscnt]=newjob
        jobq.put(newjob)
    else:
        print()