import subprocess
import sys


def yes_or_no(msg):
    while 1:
        sys.stdout.write(msg)
        sys.stdout.flush()
        inp = sys.stdin.readline()
        if inp.startswith("y"):
            return True
        return False


def shellcomm(cmd):
    print("+ %s" % cmd)
    return subprocess.check_call(cmd, shell=True)


def fail(msg):
    print("ERROR: %s" % msg)
    sys.exit(1)
