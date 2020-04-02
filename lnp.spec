# -*- mode: python -*-
# If PIL or similar is available on this system, it will be available for the
# generated executable. Since this is the only factor in whether or not we
# will be able to use non-GIF images, we only include the appropriate version.
import sys

if sys.platform == 'win32':
    try:
      from PyInstaller.utils.winmanifest import Manifest
    except ImportError:
      # Newer PyInstaller versions
      from PyInstaller.utils.win32.winmanifest import Manifest
    Manifest.old_toprettyxml = Manifest.toprettyxml
    def new_toprettyxml(self, indent="  ", newl=os.linesep, encoding="UTF-8"):
      s = self.old_toprettyxml(indent, newl, encoding)
      # Make sure we only modify our own manifest
      if 'name="lnp"' in s:
        d = indent + '<asmv3:application xmlns:asmv3="urn:schemas-microsoft-com:asm.v3"><windowsSettings xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings"><dpiAware>false</dpiAware></windowsSettings></asmv3:application>' + newl
        s = s.replace('</assembly>',d+'</assembly>')
      return s
    Manifest.toprettyxml = new_toprettyxml

try:
    from PIL import Image, ImageTk
    has_PIL = True
except ImportError: # Some PIL installations live outside of the PIL package
    try:
        import Image, ImageTk
        has_PIL = True
    except ImportError: #No PIL compatible library
        has_PIL = False

if sys.hexversion < 0x3000000: # Python 2
    from Tkinter import *
else: # Python 3
    from tkinter import *

if has_PIL or TkVersion >= 8.6:
    logo='LNPSMALL.png'
    icon='LNP.png'
else:
    logo='LNPSMALL.gif'
    icon='LNP.gif'

extension=''
script='launch.py'
if sys.platform == 'win32':
    icon='LNP.ico'
    extension='.exe'

a = Analysis(
  [script], pathex=['.'], hiddenimports=[], hookspath=None, runtime_hooks=None)
a.datas+=[(logo,logo,'DATA'),(icon,icon,'DATA')]
if sys.platform == 'win32':
    # Importing pkg_resources fails with Pillow on Windows due to
    # unnormalized case; this works around the problem
    a.datas = list({tuple(map(str.upper, t)) for t in a.datas})
pyz = PYZ(a.pure)
if sys.platform != 'darwin':
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, name='PyLNP'+extension,
        debug=False, strip=None, upx=False, console=False, icon='LNP.ico')
else:
    info = {'NSHighResolutionCapable': 'True'}
    exe = EXE(
        pyz, a.scripts, exclude_binaries=True, name='PyLNP'+extension,
        debug=False, strip=None, upx=True, console=False)
    coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=None, upx=True, name='PyLNP')
    app = BUNDLE(coll,name='PyLNP.app',icon='LNP.icns', info_plist=info)

# vim:expandtab
