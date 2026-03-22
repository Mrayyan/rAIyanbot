def calculate_area(length, width):
    """
    Calculate the area of a rectangle given its length and width.
    
    Args:
        length (float): The length of the rectangle
        width (float): The width of the rectangle
    
    Returns:
        float: The area of the rectangle
    """
    return length * width

# Test the function
if __name__ == "__main__":
    # Test cases
    print(f"Area of 5 x 3 rectangle: {calculate_area(5, 3)}")
    print(f"Area of 10.5 x 7.2 rectangle: {calculate_area(10.5, 7.2)}")
    print(f"Area of 1 x 1 rectangle: {calculate_area(1, 1)}")