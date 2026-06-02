import os
os.system('cls' if os.name == 'nt' else 'clear')
def solve_hanoi_string_output(total_disks):
    # 1. Initialize lists internally
    source = list(range(total_disks, 0, -1))
    auxiliary = []
    destination = []
    
    # Storage for each state row
    history_rows = []

    # 2. Append the current state to our history list
    def record_state():
        history_rows.append(f"{source} {auxiliary} {destination}")

    # Record the initial board setup
    record_state() 

    # 3. Recursive solver
    def move_disks(n, src_list, dest_list, aux_list):
        if n == 1:
            dest_list.append(src_list.pop())
            record_state()
            return

        # Step 1: Move n-1 disks from Source to Auxiliary
        move_disks(n - 1, src_list, aux_list, dest_list)

        # Step 2: Move the largest disk from Source to Destination
        dest_list.append(src_list.pop())
        record_state()

        # Step 3: Move n-1 disks from Auxiliary to Destination
        move_disks(n - 1, aux_list, dest_list, src_list)

    # Run the recursion
    move_disks(total_disks, source, destination, auxiliary)
    
    # 4. Join all collected row strings into one multi-line string
    return "\n".join(history_rows)


# Example usage:
print(solve_hanoi_string_output(3))
print("=========================")
print(solve_hanoi_string_output(4))
