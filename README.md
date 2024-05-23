# RPI_project

## Инструкция по запуску

Версия платы: Raspberry Pi 4b
OC: Respberry OS

- Для установки сервера плата Raspberry Pi должна быть подключена к интернету
- Подключение к серверу происходит через порт 8765
- Пины указаны в файле Pins.txt

Установка:
1. Загрузить python_server.zip в директорию /var на плате Raspberry Pi
2. Выполнить следующие команды:

cd /var
mkdir python_server
unzip python_server.zip -d /var
cd /var/python_server
sudo python -m venv venv

sudo apt install ufw
sudo ufw allow ssh
sudo ufw enable
sudo ufw allow 8765
sudo ufw reload

echo "[Unit]
Description=Python Raspberry Pi Application
[Service]
WorkingDirectory=/var/python_server
ExecStart=sudo ./venv/bin/python server.py
Restart=always
RestartSec=3
KillSignal=SIGINT
User=root
[Install]
WantedBy=multi-user.target" >> /etc/systemd/system/python-app.service
sudo systemctl daemon-reload
sudo systemctl enable python-app.service
sudo systemctl start python-app.service