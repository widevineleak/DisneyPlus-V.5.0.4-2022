@echo off
cd vinetrimmer
python AddKeysToKeyVault.py -t Amazon -i keys.txt -o key_store.db
pause