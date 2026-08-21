"""Minimal protobuf wire-format walker for .replay26 files."""
def read_varint(b,i):
    shift=val=0
    while True:
        x=b[i]; i+=1; val |= (x&0x7F)<<shift
        if not x&0x80: return val,i
        shift+=7
def parse(b,start=0,end=None):
    if end is None: end=len(b)
    i=start; out=[]
    while i<end:
        try: key,i=read_varint(b,i)
        except IndexError: break
        fn,wt=key>>3,key&7
        if wt==0:
            v,i=read_varint(b,i); out.append((fn,wt,v))
        elif wt==2:
            ln,i=read_varint(b,i); out.append((fn,wt,b[i:i+ln])); i+=ln
        elif wt==5: out.append((fn,wt,b[i:i+4])); i+=4
        elif wt==1: out.append((fn,wt,b[i:i+8])); i+=8
        else: break
    return out
