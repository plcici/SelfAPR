import numpy as np
import pandas as pd
import torch,sys
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, RandomSampler, SequentialSampler
import warnings
from torch import cuda
from transformers import T5Tokenizer, T5ForConditionalGeneration
import loader
import torch.autograd as autograd
import csv
import os
#TODO:valid、test函数的作用；训练数据集为'./dataset/SelfAPR.csv'，使用T5模型，将训练好的模型保存至./model_SelfAPR/SelfAPR'+str(epoch+1)中
#def validate_by_compiler(bugid, predstr, mode):
#gen, gen_optimizer, gen_tokenizer, adv_loader, device, epoch

def training(generator, gen_opt, gen_tokenizer, adv_loader, device,epoch):
    """
    The generator is trained using policy gradients, using the reward from the discriminator.
    Training is done for num_batches batches.
    """
    generator.train()
    #data['source_ids'].shape = torch.Size([32, 384]), data['source_mask'].shape = torch.Size([32, 384]), data['target_ids'].shape = torch.Size([32, 76]), data['target_ids_y'].shape = torch.Size([32, 76])
    for _,data in enumerate(adv_loader, 0):  #data是一个batch的数据，包括bugid、source_ids、source_mask、target_ids、target_ids_y，其中source_ids表示buggy，target_ids表示patch
        if _>0:
            y = data['target_ids'].to(device, dtype = torch.long)
            y_ids = y[:, :-1].contiguous()   #从每一行中移除了最后一列，contiguous确保得到的张量在内存中是连续的,-1是0
            lm_labels = y[:, 1:].clone().detach()  #1的位置是[PATCH]
            lm_labels[y[:, 1:] == gen_tokenizer.pad_token_id] = -100  #将lm_labels中所有对应于填充token的位置的值设置为-100
            #为什么要这么做？在训练Transformer和其他NLP模型时，一个常见的做法是将填充token的位置的标签设置为一个特定的值（通常是-100），以便模型知道在计算损失时忽略这些位置。HuggingFace's Transformers库和一些其他库默认将-100视为一个特殊的"忽略"值
            ids = data['source_ids'].to(device, dtype = torch.long)
            mask = data['source_mask'].to(device, dtype = torch.long)
            #bugid = data['bugid'].to(device, dtype = torch.long)
            #print(f'bugid: {bugid}')

            outputs = generator(input_ids = ids, attention_mask = mask, decoder_input_ids=y_ids, labels=lm_labels)  
            loss = outputs[0]  #TODO:outputs共有9个返回值，其中3个都是None，因此最终有6个，具体的内容可以看huggingface

            gen_opt.zero_grad()
            loss.backward()
            gen_opt.step()

            #we record the training log
            if _%1000 == 0:
                recordDataSimple(epoch,str(_),loss)   #将数据日志记录在'./training_log_selfaprALL.csv'中

            if _%5000 == 0:
                generator.save_pretrained('./model_SelfAPR/SelfAPR'+str(epoch+1))
                gen_tokenizer.save_pretrained('./model_SelfAPR/SelfAPR'+str(epoch+1))
            


def recordData(epoch, bugid, crossEntropLoss, reward, preds, groundTruth):
    with open('./training_log_selfaprALL.csv', 'a') as csvfile:
        filewriter = csv.writer(csvfile, delimiter='\t',quotechar='"',quoting=csv.QUOTE_MINIMAL)
        filewriter.writerow([epoch, bugid, crossEntropLoss, reward, preds,groundTruth])

def recordDataSimple(epoch,count, loss):
    with open('./training_log_selfaprALL.csv', 'a') as csvfile:
        filewriter = csv.writer(csvfile, delimiter='\t',quotechar='"',quoting=csv.QUOTE_MINIMAL)
        filewriter.writerow([epoch, count, loss])

        
        
        
def valid( model, tokenizer, device, loader,epoch):
    model.eval()
    total_loss = 0 
    total_nb=0
    total_succ = 0
    fault_locate_succ=0
    total_fail = 0
    with torch.no_grad():
        for _,data in enumerate(loader, 0):
            y = data['target_ids'].to(device, dtype = torch.long)
            y_ids = y[:, :-1].contiguous()
            lm_labels = y[:, 1:].clone().detach()
            lm_labels[y[:, 1:] == tokenizer.pad_token_id] = -100
            ids = data['source_ids'].to(device, dtype = torch.long)
            mask = data['source_mask'].to(device, dtype = torch.long)
            bugid = data['bugid'].to(device, dtype = torch.long)
            print(f'bugid: {bugid}')

            #output generation
            outputs = model(input_ids = ids, attention_mask = mask, decoder_input_ids=y_ids, labels=lm_labels)
            loss = outputs[0]
            total_nb += 1  
            total_loss += loss.item()            
            
            print(f'loss: {loss}')
            lm_logits = outputs[1]
            output = F.log_softmax(lm_logits, -1)
            preds_seq = output.max(2)[1]
            g = preds_seq[0]  
            preds = [tokenizer.decode(g, skip_special_tokens=True, clean_up_tokenization_spaces=True)]
            predstr = preds[0] 
            print(f'predstr: {predstr}')
            
            reward, result = validate_by_compiler(bugid, predstr, 'valid')
            
            if 'success' in result:
                total_succ+=1
            elif 'failedLocateBug' in result:
                total_fail+=1
            else:
                fault_locate_succ +=1
                          

        print(f'Total Loss:  {total_loss}/{total_nb}')
        with open('./valid_logs.csv', 'a') as csvfile:
            filewriter = csv.writer(csvfile, delimiter='\t',quotechar='"',quoting=csv.QUOTE_MINIMAL)
            filewriter.writerow([epoch,(total_loss/total_nb), total_succ, fault_locate_succ, total_fail ])
        


def getGeneratorDataLoader(filepatch,tokenizer,batchsize):
    df = pd.read_csv(filepatch,encoding='latin-1',delimiter='\t')
    df.columns = ['patch','buggy', 'patchRule']
    print(df.head(5))
    
    df = df[['patch','buggy']]  #只取前两列

    params = {
        'batch_size': batchsize,
        'shuffle': True,
        'num_workers': 0
        }

    dataset=df.sample(frac=1.0, random_state = SEED).reset_index(drop=True)  #打乱df的行顺序，重置索引
    target_set = loader.CustomDataset(dataset, tokenizer, MAX_LEN, PATCH_LEN)  #使用给定的参数创建一个新的自定义数据集
    target_loader = DataLoader(target_set, **params)   #为之前定义的数据集创建一个数据加载器，该数据加载器在训练和评估过程中负责高效地提供数据
    return target_loader




def run_training(epoch):
    
    if epoch == 0:
        gen = T5ForConditionalGeneration.from_pretrained("t5-base", output_hidden_states=True)      
        gen_tokenizer = T5Tokenizer.from_pretrained("t5-base",truncation=True)       
        gen_tokenizer.add_tokens(['{', '}','<','^','<=','>=','==','!=','<<','>>','[PATCH]','[BUG]','[CE]','[FE]','[CONTEXT]','[BUGGY]','[CLASS]','[METHOD]','[RETURN_TYPE]','[VARIABLES]','[Delete]'])

    else:
        gen = T5ForConditionalGeneration.from_pretrained('./model_SelfAPR/SelfAPR'+str(epoch), output_hidden_states=True)      
        gen_tokenizer = T5Tokenizer.from_pretrained('./model_SelfAPR/SelfAPR'+str(epoch),truncation=True)
                
    gen = gen.to(device)
    gen_optimizer = torch.optim.Adam(params = gen.parameters(), lr=LEARNING_RATE)


    adv_loader=getGeneratorDataLoader(TRAIN_PATH,gen_tokenizer,32)   


    print('\n--------\nEPOCH %d\n--------' % (epoch+1))
    print('\nTraining Generator : ', end='')
    training(gen, gen_optimizer, gen_tokenizer, adv_loader, device, epoch)         

    gen.save_pretrained('./model_SelfAPR/SelfAPR'+str(epoch+1))  #TODO:在training里面已经保存了一次，这里又保存一次，为什么？因为training里面是每5000次保存一次，这里是每个epoch保存一次
    gen_tokenizer.save_pretrained('./model_SelfAPR/SelfAPR'+str(epoch+1))      
        
        
if __name__ == '__main__':
    warnings.filterwarnings('ignore')
    SEED=42
    TRAIN_EPOCHS = 1
    LEARNING_RATE = 1e-4
    MAX_LEN = 384
    PATCH_LEN = 76 
    os.environ["CUDA_VISIBLE_DEVICES"] = "0, 1, 2"
    device_id = [0, 1, 2]   
    for i in range(torch.cuda.device_count()):
        print(torch.cuda.get_device_name(i), i)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    TRAIN_PATH= './dataset/train.csv'
    
    for epoch in range(0,TRAIN_EPOCHS):
        run_training(epoch)
