#!/bin/bash
set -e

CORPUS=segmentation/glove.csv.xz
VOCAB_FILE=tmp/vocab.txt
COOCCURRENCE_FILE=tmp/cooccurrence.bin
COOCCURRENCE_SHUF_FILE=tmp/cooccurrence.shuf.bin
BUILDDIR=GloVe/build
VERBOSE=2
MEMORY=8.0
VOCAB_MIN_COUNT=50
VECTOR_SIZE=10
MAX_ITER=500
WINDOW_SIZE=5
BINARY=0
NUM_THREADS=8
X_MAX=100
ETA=0.05
ALPHA=1
SAVE_FILE=segmentation/vectors-d$VECTOR_SIZE-w$WINDOW_SIZE-i$MAX_ITER

if [ ! -d $BUILDDIR ]; then
	git submodule init
	git submodule update
fi

pushd GloVe
make
popd

if [ ! -f $SAVE_FILE.txt ]; then
	echo "$ $BUILDDIR/vocab_count -min-count $VOCAB_MIN_COUNT -verbose $VERBOSE > $VOCAB_FILE"
	unxz $CORPUS -c | $BUILDDIR/vocab_count -min-count $VOCAB_MIN_COUNT -verbose $VERBOSE > $VOCAB_FILE

	echo "$ $BUILDDIR/cooccur -memory $MEMORY -vocab-file $VOCAB_FILE -verbose $VERBOSE -window-size $WINDOW_SIZE > $COOCCURRENCE_FILE"
	unxz $CORPUS -c | $BUILDDIR/cooccur -memory $MEMORY -vocab-file $VOCAB_FILE -verbose $VERBOSE -window-size $WINDOW_SIZE > $COOCCURRENCE_FILE

	echo "$ $BUILDDIR/shuffle -memory $MEMORY -verbose $VERBOSE < $COOCCURRENCE_FILE > $COOCCURRENCE_SHUF_FILE"
	$BUILDDIR/shuffle -memory $MEMORY -verbose $VERBOSE < $COOCCURRENCE_FILE > $COOCCURRENCE_SHUF_FILE
fi

echo "$ $BUILDDIR/glove -save-file $SAVE_FILE -threads $NUM_THREADS -input-file $COOCCURRENCE_SHUF_FILE -x-max $X_MAX -iter $MAX_ITER -vector-size $VECTOR_SIZE -binary $BINARY -vocab-file $VOCAB_FILE -verbose $VERBOSE"
$BUILDDIR/glove -save-file $SAVE_FILE -input-file $COOCCURRENCE_SHUF_FILE -vocab-file $VOCAB_FILE \
	-threads $NUM_THREADS -x-max $X_MAX -iter $MAX_ITER -vector-size $VECTOR_SIZE -binary $BINARY \
	-eta $ETA -alpha $ALPHA -verbose $VERBOSE

