from os import path, makedirs
import pathlib
import tarfile
# import zipfile

currentDirectory = pathlib.Path(path.join(path.dirname(__file__), 'Compress'))
for currentFile in currentDirectory.iterdir():
    try:
        uncompress_path = path.join(path.dirname(__file__), 'Uncompress/%s' % (currentFile.name.replace('.tar.gz', '')))
        # uncompress_path = path.join(path.dirname(__file__), 'Uncompress/%s' % (currentFile.name.replace('.zip', '')))
        makedirs(uncompress_path, exist_ok=False)
        print('UNZIPPING\t', currentFile, '\nINTO\t\t', uncompress_path, '\n')
        tar_ref = tarfile.open(currentFile, 'r')
        tar_ref.extractall(uncompress_path)
        tar_ref.close()
    except IOError as e:
        print('cannot unzip file, folder %s already exist' % currentFile.name)
