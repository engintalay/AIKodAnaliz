def calculate_fibonacci(n):
    """
    Fibonacci serisini hesaplar
    
    Args:
        n: Fibonacci serisinde kaçıncı pozisyon
        
    Returns:
        n. Fibonacci sayısı
    """
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    
    return b


def main():
    for i in range(10):
        print(f"Fib({i}) = {calculate_fibonacci(i)}")


if __name__ == "__main__":
    main()
