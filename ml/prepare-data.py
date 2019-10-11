import random
import re
import pickle
from collections import defaultdict

import numpy as np


def fix(line):
    line = re.subn(r'\|\d+', '', line)[0]
    line = re.subn(r'\([^)]+\)', '', line)[0]
    line = re.subn(r'\[[^]]+\]', '', line)[0]
    line = re.subn(r'\{[^}]+\}', '', line)[0]
    line = line.replace('~', '')

    return line


def make_sample(line):
    line = line.split()
    labels = []
    for word in line:
        labels.append(1)
        labels.extend(0 for _ in range(len(word) - 1))

    mapped = []
    for word in line:
        mapped.extend(mappings.get(c, len(mappings)) for c in word)

    return mapped, labels


def make_padded_arrays(sample):
    input, labels = sample
    input.extend(0 for _ in range(max_length - len(input)))
    labels.extend(0 for _ in range(max_length - len(labels)))
    return np.array(input, np.int32), np.array(labels, np.int8)


lines = []
for line in open('tmp/jpn_indices.csv'):  # http://downloads.tatoeba.org/exports/jpn_indices.tar.bz2
    line = line.strip().split('\t')
    if len(line) < 3:
        continue
    lines.append(fix(line[2]))

print(len(lines))
random.shuffle(lines)

# first split
sep = int(len(lines) * 0.8)
train, test = lines[:sep], lines[sep:]
with open('train.txt', 'w') as of:
    print(*train, sep='\n', end='', file=of)
with open('test.txt', 'w') as of:
    print(*test, sep='\n', end='', file=of)
del test

# compute mappings
counts = defaultdict(int)
for line in train:
    for c in ''.join(line.split()):
        counts[c] += 1

counts = list(counts.items())
counts.sort(key=lambda c: c[1], reverse=True)
mappings = dict((c, i + 1) for i, (c, m) in enumerate(counts[:2500]))
mappings['UNK'] = len(mappings) + 1

with open('tmp/mappings.pkl', 'wb') as of:
    pickle.dump(mappings, of)


train = list(map(make_sample, train))
max_length = max(map(lambda s: len(s[0]), train))
train = list(map(make_padded_arrays, train))
samples, labels = tuple(zip(*train))
print(len(samples), len(labels))
print(len(samples[0]), len(labels[0]))
with open('tmp/train.npy', 'wb') as of:
    np.save(of, samples)
    np.save(of, labels)
