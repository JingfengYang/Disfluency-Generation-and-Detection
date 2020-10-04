import os
import torch
from multiprocessing import Pool
from functools import partial

use_cuda = torch.cuda.is_available()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def readData(dir_name):
    sentList = []
    sent = []
    label = set()
    for file in os.listdir(dir_name):
        with open(dir_name+'/'+file, 'r',encoding='utf-8') as reader:
            for line in reader:
                content = line.strip()
                if content == '':
                    sentList.append(sent)
                    sent = []
                else:
                    tokens=content.split()
                    label.add(tokens[6])
                    sent.append([tokens[2],tokens[3], tokens[6]])
        if len(sent) > 0:
            sentList.append(sent)
            sent = []
    return sentList

def preProcess(sents):
    newSents=[]
    for sent in sents:
        sent1=[]
        sent2=[]
        for t in sent:
            if not t[0].endswith('-') and not t[0]=='SILENCE' and not t[0]=='TRACE' and not t[1]=='None':
                sent1.append(t)
        if len(sent1)<=0:
            continue
        tag = 0
        for (i,t) in enumerate(sent1):
            if t[2]=='+':
                tag = 1
                if i==0 or not sent1[i-1][2]=='+':
                    if i==len(sent1)-1 or not sent1[i+1][2]=='+':
                        sent2.append([t[0], t[1], 'I'])
                    else:
                        sent2.append([t[0],t[1],'I'])
                elif i==len(sent1)-1 or not sent1[i+1][2]=='+':
                    sent2.append([t[0], t[1], 'I'])
                else:
                    sent2.append([t[0], t[1], 'I'])
            elif t[2]=='-':
                sent2.append([t[0], t[1], 'O'])
            else:
                assert(t[2]=='None')
                sent2.append([t[0], t[1], 'O'])
        if tag==1:
            newSents.append(sent2)
    return newSents

def readFile(file):
    sents=[]
    with open(file) as reader:
        i = -1
        for line in reader:
            i += 1
            if i % 4 == 0:
                sents.append([[token] for token in line.strip().split()])
            elif i%4==1:
                for li , token in zip(sents[-1],line.strip().split()):
                    li.append(token)
            if i % 4 == 2:
                for li, token in zip(sents[-1], line.strip().split()):
                    li.append(token)
            else:
                continue

    return sents

def writeSents(sents,file):
    with open(file,'w') as writer:
        for sent in sents:
            for seq in list(zip(*sent)):
                writer.write('\t'.join(seq)+'\n')
            writer.write('\n')

def build_vocab(sents,min_count=0):###
    labels=set()

    for sent in sents:
        for token in sent:
            labels.add(token[2])
    id2label=list(labels)
    #id2label=id2label+["<pad>"]
    label2id={}
    for i,label in enumerate(id2label):
        label2id[label]=i

    return label2id,id2label

def get_idx(word,vocDic,unk=1):
    if word in vocDic:
        return vocDic[word]
    else:
        return len(vocDic)

def procs1(tokenizer,tagDic,line):
    sent=line.strip().split('\t')
    sent=[t.split() for t in sent]
    if int(sent[0][0]) % 1000000 == 1:
        print(int(sent[0][0]))
    sent=sent[1:]

    words = [token[0].lower() for token in sent]
    tags = [token[2] for token in sent]

    words = ["[CLS]"] + words + ["[SEP]"]
    tags = ["<pad>"] + tags + ["<pad>"]
    idSent = []
    idHead = []
    idTag = []
    for w, t in zip(words, tags):
        tokens = tokenizer.tokenize(w) if w not in ("[CLS]", "[SEP]") else [w]
        xx = tokenizer.convert_tokens_to_ids(tokens)

        is_head = [1] + [0] * (len(tokens) - 1)

        t = [t] + ["<pad>"] * (len(tokens) - 1)  # <PAD>: no decision
        # print(t)
        yy = [get_idx(each, tagDic) for each in t]  # (T,)
        if not len(yy)==len(xx):
            return ([],[],[])
        idSent.extend(xx)
        idHead.extend(is_head)
        idTag.extend(yy)
    if len(idSent)>150:
        #print(len(idSent))
        return ([],[],[])
    assert (len(idSent) == len(idTag))
    assert (len(idSent) == len(idHead))
    return (idSent,idHead,idTag)

def procs(tokenizer,tagDic,sent):
    assert (len(sent) > 0)
    if sent[0] % 1000000 == 1:
        print(sent[0])
    sent=sent[1]
    words = [token[0] for token in sent]
    tags = [token[2] for token in sent]
    words = ["[CLS]"] + words + ["[SEP]"]
    tags = ["<pad>"] + tags + ["<pad>"]
    idSent = []
    idHead = []
    idTag = []
    for w, t in zip(words, tags):
        tokens = tokenizer.tokenize(w) if w not in ("[CLS]", "[SEP]") else [w]
        xx = tokenizer.convert_tokens_to_ids(tokens)

        is_head = [1] + [0] * (len(tokens) - 1)

        t = [t] + ["<pad>"] * (len(tokens) - 1)  # <PAD>: no decision
        # print(t)
        yy = [get_idx(each, tagDic) for each in t]  # (T,)

        idSent.extend(xx)
        idHead.extend(is_head)
        idTag.extend(yy)
    assert (len(idSent) == len(idTag))
    assert (len(idSent) == len(idHead))
    return (idSent,idHead,idTag)

def idDataPretrain(tokenizer,tagDic,file):
    #print(tagDic)
    allHeads=[]
    allSents=[]
    allTags=[]

    ppro = partial(procs1, tokenizer, tagDic)
    pool = Pool(processes=50)
    with open(file) as reader:
        mcount=0
        for idSent, idHead, idTag in pool.imap(ppro, reader, 20000):
            if len(idSent)>0:
                allSents.append(idSent)
                allTags.append(idTag)
                allHeads.append(idHead)
            else:
                mcount+=1
        print('minus',mcount)

    pool.close()
    pool.join()
    return [allSents,allTags,allHeads]

def idData(tokenizer,sents,tagDic):
    #print(tagDic)
    tup=zip(sents,range(len(sents)))
    tup=sorted(tup,key=lambda x:len(x[0]),reverse=True)
    sents=[t[0] for t in tup]
    index=[t[1] for t in tup]
    allHeads=[]
    allSents=[]
    allTags=[]

    for sent in enumerate(sents):
        (idSent, idHead, idTag) = procs(tokenizer, tagDic, sent)
        assert (len(idSent) == len(idTag))
        assert (len(idSent) == len(idHead))

        allSents.append(idSent)
        allTags.append(idTag)
        allHeads.append(idHead)
        #allSents.append([) for token in sent])
        #allTags.append([tagDic[token[2]] for token in sent])
    #print(allTags)
    return [allSents,allTags,allHeads,index]

def padding(batch,pad=0):
    lengths=[len(sent) for sent in batch]
    ntokens=sum(lengths)
    maxLen=max(lengths)
    outbatch = []
    for sent in batch:
        outbatch.append(sent + [pad] * (maxLen - len(sent)))

    return [torch.tensor(outbatch, dtype=torch.long, device=device),
            torch.tensor(lengths, dtype=torch.long, device=device), ntokens]

def ast(t):
    s,o=t
    assert(len(s)==len(o))

def batchIter(data,batch_size,w_tag_pad=0,t_tag_pad=0,train=True):
    allSents=data[0]
    allTags=data[1]
    assert(len(allSents)==len(allTags))
    pool = Pool(processes=50)
    pool.imap(ast, zip(allSents,allTags), 20000)
    pool.close()
    pool.join()
    nbatch=len(allSents)//batch_size

    for i in range(nbatch):
        yield padding(allSents[i*batch_size:(i+1)*batch_size],pad=w_tag_pad), padding(allTags[i*batch_size:(i+1)*batch_size],pad=t_tag_pad)
    if len(allSents)>nbatch*batch_size:
        yield padding(allSents[nbatch * batch_size:],pad=w_tag_pad), padding(allTags[nbatch * batch_size:],pad=t_tag_pad)

def isEdit(id,id2label):
    if not id2label[id]=='O':
        return True
    else:
        return False
'''trainSents=preProcess(readData('dps/swbd/train'))
valSents=preProcess(readData('dps/swbd/val'))
testSents=preProcess(readData('dps/swbd/test'))
writeSents(trainSents,'train.txt')
writeSents(valSents,'val.txt')
writeSents(testSents,'test.txt')
print(stat(trainSents),len(trainSents))'''
