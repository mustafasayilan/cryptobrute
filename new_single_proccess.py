from bitcoinaddress import Wallet
import os
from multiprocessing import Process
import argparse
import sys
import signal

def handler(signum, frame):
    print('Exiting')
    sys.exit()
# Set the signal handler
signal.signal(signal.SIGINT, handler)

parser = argparse.ArgumentParser()
parser.add_argument("-o", "--output", action='store', dest='output', help="Results will write this file.")
parser.add_argument("-p", "--maxprocess", action='store', dest='maxprocess', help="Maximum process. Default 5")
parser.add_argument("-i", "--input", action='store', dest='input', help="Select input address file")


args = parser.parse_args()
inputFileName = ""
outputFileName = ""
maximumProcess = 5
if args.input:
    inputFileName = args.input
else:
    sys.exit("Please select input file with -i addresses.txt")
    
if args.output:
    outputFileName = args.output
else:
    sys.exit("Please select output file with -o results.txt")
    
if args.maxprocess:
    maximumProcess = int(args.maxprocess)


global addressArray
addressArray = {}
class read:
    def readFromText():
        print("Addresses loading please wait...")
        addrfile = open(inputFileName, 'r')
        Lines = addrfile.readlines()
        for line in Lines:
            addressArray[line.rstrip('\n')] = ""
        return 1
        print("Addresses Loaded")
class save:

    def toFile(text):
        file = open(outputFileName, "a+")
        file.write(text)
        file.close()


class check:
    def balance(address):
        balances = 0
        try:
            if address in addressArray:
                balances = 1
            else:
                balances = 0
        except NameError:
            print("Error : "+str(NameError)+" Address : "+address)
            pass

        return balances

class cm:
    total = 0
    founded = 0
    def multitask():
        i = 0
        balance = 0
        found = 0
        
        while True:
            
            i += 1
            rands   = os.urandom(32).hex()
            wallet  = Wallet(rands)
            addr1   = wallet.address.__dict__['mainnet'].__dict__['pubaddr1'] 
            addr2   = wallet.address.__dict__['mainnet'].__dict__['pubaddr1c']
            heks    = wallet.key.__dict__['mainnet'].__dict__['wif']
            try:
               
                balance = float(check.balance(addr1))
                balance += float(check.balance(addr2))
                cm.total =  i
                cm.founded = found
                #if (i*5)%10000 == 0:
                if i%10000 == 0:
                    print("" + addr2+" \n  " + addr1+" \n \n Privatekey uncompressed "+heks+" i "+str(i) ,end = "\n \n")
                
                print(" Total: "+str(cm.total)+" Founded: " + str(cm.founded) ,end = "\r")
                
                        
            except NameError:
                print(str(NameError))
                pass

            res = "Count: %s | Hex: %s | Add1: %s | Add2 %s \n" % (i, heks,addr1,addr2)
            if balance > 0:
                save.toFile(res)
                found += 1
                balance = 0
                #print(res)

if __name__ == "__main__":

    if(read.readFromText() == 1):
        cm.multitask()
        
