import os
def generate_aes_key():
    key = os.urandom(32)
    return key.hex()
list_of_secrets = [ generate_aes_key()  for count in range(10)]
def choose_best_keys(keys):
    def entropy(key):
        return sum([ord(c) for c in key])/len(key)
    sorted_keys = sorted(keys , key = entropy, reverse=True)
    BEST_KEY = sorted_keys[0]
    return BEST_KEY
final_key = choose_best_keys(list_of_secrets)
print( f'Final best key is given by  : {final_key}')
