#!/bin/bash

echo Initializing default Dukascopy configuration...

mkdir -p config.user
cp -r config/* config.user/
sed 's|config/dukascopy|config.user/dukascopy|g' config.dukascopy-mt4.yaml > config.user.yaml

echo Done.