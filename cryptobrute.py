from bitcoinaddress import Wallet
import os
from multiprocessing import Process
import argparse
import sys
# Initiate the parser
parser = argparse.ArgumentParser()
parser.add_argument("-o", "--output", action='store', dest='output', help="Results will write this file.")
parser.add_argument("-i", "--input", action='store', dest='input', help="Select input address file")
# Read arguments from the command line
args = parser.parse_args()
inputFileName = ""
outputFileName = ""

if args.input:
    inputFileName = args.input
else:
    sys.exit("Please select input file with -i addresses.txt")
    
if args.output:
    outputFileName = args.input
else:
    sys.exit("Please select output file with -o results.txt")



global addressArray
addressArray = {}
class read:
    def readFromText():
        addrfile = open(inputFileName, 'r')
        Lines = addrfile.readlines()
        for line in Lines:
            addressArray[line.rstrip('\n')] = ""
        print("addresses readed")
class save:

    def toFile(text):
        file = open(outputFileName, "a+")
        file.write(text)
        file.close()


class check:
    def balance(address):
        balance = 0
        try:
            if address in addressArray:
                balance = 1
            else:
                balance = 0
        except NameError:
            pass

        return balance

class cm:
    toplam = 0
    bulunan = 0
    def coklu(pss):
        i = 0
        balance = float(0)
        found = 0
        while True:
            i += 1
            rands   = os.urandom(32).hex()
            wallet  = Wallet(rands)
            addr1   = wallet.address.__dict__['mainnet'].__dict__['pubaddr1'] 
            addr2   = wallet.address.__dict__['mainnet'].__dict__['pubaddr1c']
            addr3   = wallet.address.__dict__['mainnet'].__dict__['pubaddr3']
            addr4   = wallet.address.__dict__['mainnet'].__dict__['pubaddrbc1_P2WPKH'] 
            addr5   = wallet.address.__dict__['mainnet'].__dict__['pubaddrbc1_P2WSH'] 
            heks    = wallet.key.__dict__['mainnet'].__dict__['wif']
            try:

                balance = float(check.balance(addr1))
                balance += float(check.balance(addr2))
                balance += float(check.balance(addr3))
                balance += float(check.balance(addr4))
                balance += float(check.balance(addr5))
                cm.toplam += 5*7
                cm.bulunan += found
                if (i*5)%10000 == 0:
                    print("Worker :"+pss+" Check: " + addr1+" - "+heks + " i "+str(i*5) ,end = "\n")
                if pss == "1":
                    print(" Total: "+str(cm.toplam)+" Founded: " + str(cm.bulunan) ,end = "\r")
                
                        
            except NameError:
                print(str(NameError))
                pass

            res = "Count: %s | Hex: %s  \n" % (i, heks)
            if balance > 0:
                found += 1
                save.toFile(res)
                print(res)

if __name__ == "__main__":

    read.readFromText()

    processes = [Process(target=cm.coklu, args=("1",)),
                 Process(target=cm.coklu, args=("2",)),
                 Process(target=cm.coklu, args=("3",)),
                 Process(target=cm.coklu, args=("4",)),
                 Process(target=cm.coklu, args=("5",)),
                 Process(target=cm.coklu, args=("6",)),
                 Process(target=cm.coklu, args=("7",))]

    
    for process in processes:
        process.start()

    for process in processes:
        process.join()