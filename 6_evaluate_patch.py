#!/usr/bin/python
import sys, os, time, subprocess,fnmatch, shutil, csv,re, datetime
#此文件的作用是：执行预测的补丁，得到其执行结果，即[CE]、[FE]、[Plausible]、[OK]、[timeout]、[Identical]


#如果预测的补丁与真实的补丁不同，则将buggy项目checkout到本地，将预测的补丁写入buggy项目中，用execute函数执行预测的补丁，得到其执行结果，即[CE]、[FE]、[Plausible]、[OK]、[timeout]、[Identical]
def executePatch(projectId,bugId,startNo,removedNo,fpath,predit,repodir):
    #first checkout buggy project
    os.system('defects4j checkout -p '+ str(projectId)+' -v '+str(bugId)+'b   -w '+repodir+'/'+projectId+bugId)
    #keep a copy of the buggy file
    originFile = repodir+'/'+projectId+bugId+'/'+fpath
    filename = originFile.split('/')[-1]

    os.system("cp "+originFile+"  "+repodir)  #先将java文件复制到当前工作目录SelfAPR下
    newStr=''
    endNo=int(startNo)+int(removedNo)  #endNo表示要删除的行数
    with open(originFile,'r') as of:
        lines=of.readlines()
        for i in range(0,len(lines)):
            l=lines[i]
            if i+1 < int(startNo):
                newStr+=l 
            if i+1 == int(startNo):     #如果是buggy line的前一行，则将预测的内容与其拼接
                newStr+=predit+'\n'
            if i+1 >= endNo:
                newStr+=l
    with open(originFile,'w') as wof:
        wof.write(newStr)
#将SelfAPR的Closure-152项目下的相关java文件进行修改，即有bug代码修改为预测的补丁代码
    exeresult = execute(projectId+bugId,repodir,originFile,repodir+'/'+projectId+bugId)  #exeresult是执行预测的补丁的结果，确定其是[FE]还是[CE]
        
    os.system("mv "+repodir+"/"+filename +"  "+originFile) #将暂存于SelfAPR下的java文件移动至原本的SelfAPR/Closure152/下的文件，因为之前对SelfAPR/Closure152/修改为预测补丁的代码

    return exeresult


    
            

# defects4j compile查看编译结果，编译的目标是/home/sunwanqi/caowy/APR/SelfAPR/Chart1下的java文件，这些java文件都已被修改为预测的补丁，简单来说是查看预测的结果
# projectId+bugId,repodir,originFile,repodir+'/'+projectId+bugId；即Chart1, /home/sunwanqi/caowy/APR/SelfAPR, /home/sunwanqi/caowy/APR/SelfAPR/Chart1/xxx.java, /home/sunwanqi/caowy/APR/SelfAPR/Chart1
def execute(patchId,repodir,originFile,rootdir):
    compile_error_flag = True

    program_path=repodir+'/'+patchId   #/home/sunwanqi/caowy/APR/SelfAPR/Chart1
    print('****************'+program_path+'******************')
    #get compile result
    cmd = "cd " + program_path + ";"
    cmd += "timeout 90 defects4j compile"
    exectresult='[timeout]'
    symbolVaraible=''
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  
    print(result)
    
    # evaluate compilable
    if 'Running ant (compile)' in str(result):  #表明之前正在尝试编译项目
        result = str(result).split("Running ant (compile)")[1]
        result=result.split('\n')
        for i in range(0,len(result)):
            if 'error: ' in result[i]:
                firstError=result[i].split('error: ')[1]   #提取错误内容。注意这里只处理第一个遇到的错误
                exectresult=firstError.split('[javac]')[0]
                if '\\' in exectresult:
                    exectresult=exectresult.split('\\')[0]
                print('=======First Error========='+firstError)
                # 'cannot  find  symbol      
                if 'symbol' in firstError and 'cannot' in firstError and 'find' in firstError:       
                    if '[javac]' in firstError:  #编译错误信息的一部分，其中可以找到具体的符号错误信息
                        lines = firstError.split('[javac]')
                        for l in lines:
                            if 'symbol:'in l and 'variable' in l:
                                symbolVaraible=l.split('variable')[1]
                                if '\\' in symbolVaraible:
                                    symbolVaraible=symbolVaraible.split('\\')[0]
                                break



                exectresult='[CE] '+exectresult+symbolVaraible
                break
            elif 'OK' in result[i]:               
                exectresult='OK'
                compile_error_flag=False

    # evaluate plausible
    if not compile_error_flag:
        #get test result
        cmd = "cd " + program_path + ";"
        cmd += "timeout 120 defects4j test"
        result=''
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        print(result)
        if 'Failing tests: 0' in str(result):
            exectresult='[Plausible]'
        elif 'Failing tests' in str(result):
            result=str(result).split('Failing tests:')[1]
            result=str(result).split('-')
            for i in range(1,len(result)):
                failingtest = result[i]
                if '::' not in failingtest and i+1<len(result):
                    failingtest = result[i+1]
                if '\\' in failingtest:
                    failingtest = failingtest.split('\\')[0]
                failingtest=failingtest.strip()

                if '::' in failingtest:
                    failingTestMethod=failingtest.split('::')[1]
                    faildiag = getFailingTestDiagnostic(failingtest,program_path)
                    exectresult = '[FE] ' + faildiag +' '+failingTestMethod
                else:
                    exectresult = '[FE] '
                break
   
    os.chdir(rootdir)

    return exectresult


def getFailingTestDiagnostic(failingtest,program_path):
    testclass = failingtest.split("::")[0]

    cmd = "cd " + program_path + ";"
    cmd += "timeout 120 defects4j monitor.test -t "+failingtest
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    print('====result===='+str(result))
    if 'failed!' in str(result) :
        result = str(result).split('failed!')[1]
        if testclass in str(result):
            result = str(result).split(testclass)[1]
            if '):' in str(result):
                result = str(result).split('):')[1]
                if '\\' in str(result):
                    result = str(result).split('\\')[0]
    else:
        result =''

    return str(result)


if __name__ == '__main__':
    #raw_result.csv的内容：bugname, startNo,removeNo,filepath,preds[i],target]
    patchFromPath='./raw_results.csv'  #5_test.py的结果
    patchToPath='./results.csv'   
    repodir = '/home/sunwanqi/caowy/APR/SelfAPR'    


    with open(patchFromPath,'r') as patchFile:
        patches = patchFile.readlines()
        for i in range(0,1):
            try:
                print(i)
                patch=patches[i]
                print(patch)
                pid=patch.split('\t')[0]
                projectId =pid.split('_')[0]
                bugId =pid.split('_')[1]
                startNo=patch.split('\t')[1]
                removedNo=patch.split('\t')[2]
                path=patch.split('\t')[3]
                predit = patch.split('\t')[4]
                groundtruth = patch.split('\t')[5]

                print(patch)
                print(projectId)
                print(bugId)

                preditNoSpace = predit.replace(' ','').replace('\n','').replace('\r','').replace('[Delete]','')
                groundtruthNoSpace = groundtruth.replace(' ','').replace('\n','').replace('\r','').replace('[PATCH]','').replace('[Delete]','')
                if groundtruthNoSpace in 'nan':
                    groundtruthNoSpace=''
                if preditNoSpace in groundtruthNoSpace and groundtruthNoSpace in preditNoSpace:  #如果预测的补丁和真实的补丁相同
                    with open(patchToPath,'a') as targetFile:
                        targetFile.write('Identical\t'+str(i)+'\t'+patch)
                else:
                    exeresult = executePatch(projectId,bugId,startNo,removedNo,path,predit,repodir)  #执行预测的补丁，参数分别是Closure、152、871、1、'src/com/google/javascript/rhino/jstype/FunctionType.java'、预测的补丁和'/home/sunwanqi/caowy/APR/SelfAPR'
                    with open(patchToPath,'a') as targetFile:
                        targetFile.write(exeresult+'\t'+str(i)+'\t'+patch)
            except (IndexError, RuntimeError, TypeError, NameError,FileNotFoundError):
                print(RuntimeError)
                




