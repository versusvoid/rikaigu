#!/usr/bin/env python3

import pickle
import numpy as np
import tensorflow as tf
import random
from tensorflow import keras
from tensorflow.keras import layers

with open('tmp/train.npy', 'rb') as f:
    samples = np.load(f)
    labels = np.load(f)

print(samples.shape)
print(labels.shape)

train = list(zip(samples, labels))
random.shuffle(train)
sep = int(len(train) * 0.8)

samples = np.array(list(map(lambda p: p[0], train)))
labels = np.array(list(map(lambda p: p[1], train)))

train_batches = tf.data.Dataset.from_tensor_slices((samples[:sep], labels[:sep])).batch(16)
test_batches = tf.data.Dataset.from_tensor_slices((samples[sep:], labels[sep:])).batch(16)


mappings = pickle.load(open('tmp/mappings.pkl', 'rb'))

#input_length = len(samples[0])
output_length = labels.shape[1]
dropout_rate = 0.3
filters = 16
kernel_size = 3

model = keras.Sequential([
    #layers.Embedding(len(mappings) + 1, 24, mask_zero=True, input_length=input_length),
    layers.Embedding(len(mappings) + 1, 24, mask_zero=True),

    layers.Dropout(rate=dropout_rate),
    layers.SeparableConv1D(
        filters=filters,
        kernel_size=kernel_size,
        activation='relu',
        bias_initializer='random_uniform',
        depthwise_initializer='random_uniform',
        padding='same',
    ),
    layers.SeparableConv1D(
        filters=filters,
        kernel_size=kernel_size,
        activation='relu',
        bias_initializer='random_uniform',
        depthwise_initializer='random_uniform',
        padding='same',
    ),
    layers.MaxPooling1D(pool_size=4),

    layers.SeparableConv1D(
        filters=filters * 2,
        kernel_size=kernel_size,
        activation='relu',
        bias_initializer='random_uniform',
        depthwise_initializer='random_uniform',
        padding='same',
    ),
    layers.SeparableConv1D(
        filters=filters * 2,
        kernel_size=kernel_size,
        activation='relu',
        bias_initializer='random_uniform',
        depthwise_initializer='random_uniform',
        padding='same',
    ),
    layers.GlobalAveragePooling1D(),
    layers.Dropout(rate=dropout_rate),
    layers.Dense(output_length, activation='sigmoid'),
])

model.summary()

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy'],
)

history = model.fit(
    train_batches,
    epochs=10,
    validation_data=test_batches,
    validation_steps=20,
)
