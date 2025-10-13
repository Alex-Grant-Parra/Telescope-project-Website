import time

def timer(func):
    # Decorator to measure execution time of a function.
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"Function '{func.__name__}' executed in {duration:.6f} seconds.")
        return result
    return wrapper
