#!/bin/sh

if [ ! -f $2 ]; then
	curl \
		--location \
		--continue-at - \
		$1 \
		--output $2-part \
		--create-dirs \
		&& mv $2-part $2
	exit $?
fi
