
def l1(data: str) -> str:
    
    return "".join([c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(data)])


def l2(data: str) -> str:
    """abc -> A B C"""
    return " ".join([i.uppper() for i in data.split()])


def l3(data: str):
    """abc def -> abc's def's"""
    return " ".join([i + "'s" for i in data.split(" ")])

def l4(data: str):
    T = {
        "i": "!",
        "e": "3",
        "s": "$",
        "a": "4",
        "o": "0",
    }
    output = data
    for c1, c2 in T.items():
        output = output.replace(c1, c2)
    return output



