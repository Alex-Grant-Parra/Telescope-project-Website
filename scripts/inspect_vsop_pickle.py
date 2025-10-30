import pickle
p='instance/ephemerisData/pickled/vsop.pkl'
with open(p,'rb') as f:
    data=pickle.load(f)
print('TYPE:', type(data))
if isinstance(data, dict):
    keys = list(data.keys())
    print('NUM KEYS:', len(keys))
    print('SAMPLE KEYS (first 20):', keys[:20])
    # inspect one entry
    sample = data[keys[0]]
    print('\nSAMPLE ENTRY KEY:', keys[0])
    print('Entry type:', type(sample))
    if isinstance(sample, dict):
        subkeys = list(sample.keys())
        print('Subkeys (first 20):', subkeys[:20])
        # if subkeys look like planet names, inspect one
        if len(subkeys) > 0:
            s0 = sample[subkeys[0]]
            print('\nSample subkey:', subkeys[0], 'type', type(s0))
            if isinstance(s0, dict):
                print('  L len, B len, R len:', len(s0.get('L',[])), len(s0.get('B',[])), len(s0.get('R',[])))
                print('  First L terms:', s0.get('L',[])[:3])
else:
    print('Not a dict; type:', type(data))
