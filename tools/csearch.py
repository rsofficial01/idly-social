import sys, time
sys.path.insert(0, '/home/claude/statics')
from commons import search
for t in sys.argv[1:]:
    print('\n##', t)
    for r in search(t, 12):
        print(' | '.join(str(x) for x in r[:5]))
    time.sleep(3)
