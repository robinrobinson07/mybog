def access_path(path: str, obj: dict):
    """Truy cập một dict dựa vào đường dẫn của nó.
    Ví dụ như là a.b.c -> obj[a][b][c]
    """

    p = path.split(".")
    destination = obj
    for i in p:
        destination = destination.get(i)
    return destination
