
all: train

train: trainer.cpp feature_extractor.hpp filter_feature_index.cpp
	g++ -std=c++14 -O3 -Wall -ggdb trainer.cpp \
		-DDLIB_NO_GUI_SUPPORT=1 \
		-DDLIB_USE_BLAS=1 \
		-DDLIB_USE_LAPACK=1 \
		-DUSE_AVX_INSTRUCTIONS=1 \
		-DNO_MAKEFILE=1 \
		-pthread -lcblas -llapack \
		-o train
