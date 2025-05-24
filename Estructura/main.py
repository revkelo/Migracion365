# main.py
from migrator import DirectMigrator

if __name__ == "__main__":
    migrator = DirectMigrator(onedrive_folder="")
    migrator.migrate(skip_existing=True)
