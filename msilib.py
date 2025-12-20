# msilib.py (stub for Linux/Heroku)
class _MSILibNotAvailable(RuntimeError):
    pass

def __getattr__(name):
    raise _MSILibNotAvailable("msilib is Windows-only")
