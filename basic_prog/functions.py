# define function
def add_number(input1, input2):
  sum = input1 + input2
  # print(sum)
  return sum


print(add_number(1, 2))

def evaluate_temp(temp):
    # Set an initial message
    message = "Normal temperature."
    # Update value of message only if temperature greater than 38
    if temp > 38:
        message = "Fever!"
    return message

print(evaluate_temp(37))


set_a = {1, 2, 3, 4}
set_b = {2, 3, 4, 5, 6}

set_a.union(set_b)
set_a.intersection(set_b)
set_a.symmetric_difference(set_b)
set_a.difference(set_b)

print(set_a | set_b)
print(set_a & set_b)
print(set_a ^ set_b)
print(set_a - set_b)