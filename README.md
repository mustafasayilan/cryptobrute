# Cryptobrute
===========

Bitcoin and crypto Brute Force 2021 2022 

This project creating randomly bitcoin address and checking your address list. If created address in your list , it will save your result file. 
This project not for steal money. This project for understand about crypto money.

Disclaimer
----------
Just because you *can* steal someone's money doesn't mean you *should*.
Stealing would make you a jerk. Don't be a jerk.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

(From Brainflayer with respect)

Build
--------

Thanks for https://github.com/fortesp/bitcoinaddress 

Packages should install with

```
pip install bitcoinaddress
pip install argparse
pip install multiprocessing
```
(python 3 allready has multiprocessing)

Usage
-----

### Basic
You need a txt file containing the bitcoin addresses with the balance line by line.
You can check addressesExample.txt file
(tested with python version 3)
```
python cryptobrute.py -i address.txt -o results.txt
-p, --maxprocess N          N points per thread (default 3)
-i, --in FILE           Read text from FILE, one per line
-o, --out FILE          Write keys to FILE
```

### Supporting this project

If you find this project useful and would like to support it, consider making a donation. Your support is greatly appreciated!


```
BTC:	bc1qyphxe9pdxrje04c2eyew38e3x3stsnqdgun9jp
ETH:	0xf5AdD9f1fd00bf350a89a503D5A96949845a1a2A
DOGE:	D9J9vKf2SqDeT1FT74VLrCpUha71BiJNH2
```
