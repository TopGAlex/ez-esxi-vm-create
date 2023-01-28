
```
python -m venv env

# for windows
.\env\Scripts\activate
# for linux
source env/bin/activate

python -m pip install -r requirements.txt
```


```
python esxi-vm-create -H 192.168.1.180 -P password -u
python esxi-vm-create.py -n testvm04 --summary --iso kali-linux-2022.3-installer-amd64.iso
```