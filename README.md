# IOTA-MSS

IOTA-MSS is decentralised music streaming application which uses the distributed ledger IOTA. This platform allow musicians to share their music, have full control over its market price and be rewarded in real-time as users enjoy them. It also allows users to listen to their favourite
songs, only pay for the parts they request and distribute them to others for a fair compensation.

This repository is part of my Research Project: [IOTA-MSS: A Pay-per-Play Music Streaming System based on IOTA](IOTA_MSS_Research_Final.pdf)

A demonstration of how the platform works can be seen in the following video:

[![IMAGE ALT TEXT](https://i.ytimg.com/vi/HdMOxa9aIfg/hqdefault.jpg?sqp=-oaymwE2CNACELwBSFXyq4qpAygIARUAAIhCGAFwAcABBvABAfgB_gmAAtAFigIMCAAQARhfIF8oXzAP&rs=AOn4CLDRQU81XC1esQ_2sJhAuSXaMYn6jQ)](https://youtu.be/HdMOxa9aIfg "IOTA-MSS demo video")

This repository contains all the code necessary to run the platform. The distributed ledger can be built using the [docker-compose](docker-compose.yml) file. The smart contract can be deployed using Remix and MetaMask and its code can found [here](contract/Platform.sol). Finally, the client can be used by running the following python code [iotamss.py](iotamss.py)
