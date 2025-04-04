"""
Create standalone directory with cx_Freeze, then zip it.
"""

import os
import sys
import shutil
import subprocess


version = '0.5'


main_path = os.path.normpath(
    f'{os.path.dirname(__file__)}/polarsgraph/__main__.py')

# Define paths
release_root = sys.argv[-1]
if not os.path.isdir(release_root):
    raise ValueError('Please provide existing directory as script arg')

release_dir = os.path.normpath(f'{release_root}/polarsgraph')
zip_path = os.path.normpath(f'{release_root}/polarsgraph-{version}')

# Remove old
print('Cleaning previous releases...')
if os.path.isdir(release_dir):
    shutil.rmtree(release_dir)

if os.path.exists(zip_path):
    os.remove(zip_path)

# cx_Freeze
print('Packaging with cx_Freeze...\n')
os.makedirs(release_dir)
cxfreeze_path = f'{os.path.dirname(sys.executable)}/Scripts/cxfreeze.exe'
subprocess.check_call([
    cxfreeze_path,
    '--script', main_path,
    '--target-dir', release_dir,
    '--base', 'Win32GUI',
    '--target-name', 'PolarsGraph'])

shutil.copy2('LICENSE', release_dir)
shutil.copy2('README.md', release_dir)

# Archive
print(f'Zipping to "{zip_path}.zip"...')
shutil.make_archive(zip_path, 'zip', release_dir)
print('Release finished\n')
