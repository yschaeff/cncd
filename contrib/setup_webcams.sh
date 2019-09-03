#!/bin/bash

set -e

INSTALL_DIR=/opt

apt install cmake libjpeg62-turbo-dev gcc g++
#apt install cmake libjpeg8-dev gcc g++

useradd -r -c "Webcam system user" -G video webcamd || echo "User already exists"

cd ${INSTALL_DIR}
if [ ! -d mjpg-streamer ];
then
	mkdir -p mjpg-streamer
	chown cnc:cnc-operators mjpg-streamer
	sudo -u cnc git clone https://github.com/jacksonliam/mjpg-streamer.git mjpg-streamer
else
	cd mjpg-streamer
	sudo -u cnc git pull
fi
cd ${INSTALL_DIR}/mjpg-streamer/mjpg-streamer-experimental/
sudo -u cnc make
make install

index=0
devs=$(ls /dev/v4l/by-id/)

if [ -n "$devs" ];
then
    echo "Adding start scripts for the webcams."
    read -p "What username should I set? " user
    read -p "What password should I set? " password
fi

for dev in $devs; do 
    while [ 1 ]; do
        read -p "Found v4l device $dev. Add? <yn> " answer
        case $answer in
            [YyNn]* )break;;
            * ) echo "Please answer y or n.";;
        esac
    done

    case $answer in
        [Yy]* )
            cat > /lib/systemd/system/webcam${index}.service << EOF
[Unit]
Description=Webcam${index} mjpg_streamer
StartLimitInterval=10
StartLimitBurst=2

[Service]
ExecStart=/usr/local/bin/mjpg_streamer -o "output_http.so -w ./wwww -p $((index+31416)) -l 0.0.0.0 -c ${user}:${password} -n" -i "input_uvc.so -d /dev/v4l/by-id/${dev}"
User=webcamd
Group=video
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
            systemctl daemon-reload
            systemctl enable webcam${index}
            index=$((index+1))
            ;;
        [Nn]* ) continue;;
    esac
done

