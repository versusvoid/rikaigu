#!/bin/bash
set -e

CORPUS=segmentation/glove.csv.xz
VOCAB_FILE=vocab.txt
COOCCURRENCE_FILE=cooccurrence.bin
COOCCURRENCE_SHUF_FILE=cooccurrence.shuf.bin
BUILDDIR=GloVe/build
SAVE_FILE=vectors
VERBOSE=2
MEMORY=8.0
VOCAB_MIN_COUNT=50
VECTOR_SIZE=15
MAX_ITER=10000
WINDOW_SIZE=5
BINARY=2
NUM_THREADS=4
X_MAX=100
ETA=0.05
ALPHA=0.95

if [ ! -d $BUILDDIR ]; then
	git submodule init
	git submodule update
fi

pushd GloVe
make
popd

echo "$ $BUILDDIR/vocab_count -min-count $VOCAB_MIN_COUNT -verbose $VERBOSE > $VOCAB_FILE"
unxz $CORPUS -c | $BUILDDIR/vocab_count -min-count $VOCAB_MIN_COUNT -verbose $VERBOSE > $VOCAB_FILE

echo "$ $BUILDDIR/cooccur -memory $MEMORY -vocab-file $VOCAB_FILE -verbose $VERBOSE -window-size $WINDOW_SIZE > $COOCCURRENCE_FILE"
unxz $CORPUS -c | $BUILDDIR/cooccur -memory $MEMORY -vocab-file $VOCAB_FILE -verbose $VERBOSE -window-size $WINDOW_SIZE > $COOCCURRENCE_FILE

echo "$ $BUILDDIR/shuffle -memory $MEMORY -verbose $VERBOSE < $COOCCURRENCE_FILE > $COOCCURRENCE_SHUF_FILE"
$BUILDDIR/shuffle -memory $MEMORY -verbose $VERBOSE < $COOCCURRENCE_FILE > $COOCCURRENCE_SHUF_FILE

echo "$ $BUILDDIR/glove -save-file $SAVE_FILE -threads $NUM_THREADS -input-file $COOCCURRENCE_SHUF_FILE -x-max $X_MAX -iter $MAX_ITER -vector-size $VECTOR_SIZE -binary $BINARY -vocab-file $VOCAB_FILE -verbose $VERBOSE"
$BUILDDIR/glove -save-file $SAVE_FILE -input-file $COOCCURRENCE_SHUF_FILE -vocab-file $VOCAB_FILE \
	-threads $NUM_THREADS -x-max $X_MAX -iter $MAX_ITER -vector-size $VECTOR_SIZE -binary $BINARY \
	-eta $ETA -alpha $ALPHA -verbose $VERBOSE

