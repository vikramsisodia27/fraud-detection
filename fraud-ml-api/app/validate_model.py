THRESHOLD = 0.90

accuracy = 0.95

if accuracy >= THRESHOLD:
    print("Validation Passed")
else:
    raise Exception("Validation Failed")
