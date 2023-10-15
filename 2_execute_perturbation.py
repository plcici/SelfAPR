#!/usr/bin/python
import sys, os, time, subprocess,fnmatch, shutil, csv,re, datetime
#主要是使用不同项目的扰动java文件构建训练数据，并使用了扰动前的java文件来获取上下文信息
#对扰动后的java文件进行遍历，对每个java文件的每一行扰动数据，使用constructTrainSample函数构造训练样本，其中使用diagnostic函数得到诊断信息，其余是从扰动后的java文件中获取的数据，并保存到Samples_SelfAPR文件夹下的csv文件，最终所有的训练数据都在/dataset/SelfAPR.csv文件中
#只从扰动前的项目中获取上下文信息，上下文信息也包含了扰动后的buggy代码 
#TODO:diagnostic、executePerturbation、getFailingTestDiagnostic、getFailingTestSourceCode函数没有调用，诊断以及测试执行信息如何加入的？？buggy line后面的四行内容是什么？？
#扰动后的java文件内容主要包括 扰动规则、buggy line、开始行、结束行、groundtruth、metaInfo

def start(bugId,repodir,rootdir): 
    projectPath=repodir+'/'+bugId   #'/home/sunwanqi/caowy/APR/SelfAPR/Samples_SelfAPR/Perturbation-Lang-65'
    traveProject(bugId, projectPath,repodir)

def traveProject(bugId,projectPath,repodir):  #遍历扰动后的项目，寻找.java文件，对于每一行扰动数据，使用constructTrainSample函数构造训练样本
    listdirs = os.listdir(projectPath)
    for f in listdirs:
        pattern = '*.java'
        p = os.path.join(projectPath, f) #具体遍历的文件或者文件夹地址
        if os.path.isfile(p):
            if fnmatch.fnmatch(f, pattern) and ('Test' not in p and 'test' not in p) :
                print(p)
                with open(p,'r') as perturbFile:
                    lines = perturbFile.readlines()  #遍历使用扰动规则扰动后的java代码，同一个java文件可能有多行扰动
                    if len(lines)>0:
                        for k in range(0,len(lines)):
                            constructTrainSample(bugId, lines[k], p, repodir, True, rootdir)  #bugId是'Perturbation-Lang-65',对每一行扰动样本，构造训练样本
                            #pass
        else:
            traveProject(bugId,p,repodir)





def constructTrainSample(bugId,line,targetfile,repodir,diagnosticFlag,rootdir):
    project = bugId.split('-')[0]
    print(line)
    sample=''
    cxt=''
    filename = targetfile.split('/')[-1]
    originFile = targetfile.replace("Perturbation-","")

    if not '^' in line:
        return
    infos = line.split('^')
    if len(infos) < 11:
        return
    if len(infos) > 11:  #TODO:为什么是11，中间为什么有很多空的^，可能与具体的扰动规则有关
        return
    curruptCode =  infos[1]


    lineNo1 =  infos[2] #buggy line
    lineNo2 =  infos[3] 
    lineNo3 =  infos[4] 
    lineNo4 =  infos[5]
    lineNo5 =  infos[6]
    cxtStart = infos[7]   #上下文的行号
    cxtEnd = infos[8]
    groundTruth = infos[9]
    metaInfo = infos[10]
    groundTruth = groundTruth.replace('  ',' ').replace('\r','').replace('\n','')
    action = infos[0] 

    try:
        string_int = int(lineNo1)
    except ValueError:
        return
    

    curruptCode = curruptCode.replace(' (','(').replace(' )',')')
    curruptCode = curruptCode.replace('(  )','()')
    curruptCode = curruptCode.replace(' .','.')
    
    # get diagnostic by execution
    diagnosticMsg = diagnostic(bugId,line,targetfile,repodir,action,diagnosticFlag,rootdir)
    #diagnosticMsg = ' '
    #get context info
    if cxtStart not in '' and cxtEnd not in '':
        with open(originFile,'r') as perturbFile:   #originFile是扰动前的文件，遍历原始文件，获取上下文信息
            lines = perturbFile.readlines()
            for i in range(0,len(lines)):
                if i > int(cxtStart)-2 and i < int(cxtEnd):   #如果在上下文范围内，就把上下文的代码加入到cxt中，即获取上下文代码信息标注buggyline
                    l = lines[i]
                    l = l.strip()
                    #remove comments
                    if  l.startswith('/') or l.startswith('*'):
                        l = ' '
                    l = l.replace('  ','').replace('\r','').replace('\n','')
                    if i == int(lineNo1)-1:
                        l='[BUGGY] '+curruptCode + ' [BUGGY] '  #标注bug行
                    cxt+=l+' '
                if i > int(cxtEnd):
                    break


    os.system("mv "+repodir+"/"+filename +"  "+originFile)  # mv '/home/sunwanqi/caowy/APR/SelfAPR/Samples_SelfAPR/ValuedEnum.java  /home/sunwanqi/caowy/APR/SelfAPR/Samples_SelfAPR/Lang-65/src/java/org/apache/commons/lang/enums/ValuedEnum.java'
    sample+='[BUG] [BUGGY] ' + curruptCode + diagnosticMsg+ ' [CONTEXT] ' + cxt +' '+'  '+ metaInfo
    sample = sample.replace('\t',' ').replace('\n',' ').replace('\r',' ').replace('  ',' ') #'[BUG] [BUGGY] private static final short serialVersionUID = -7129650521543789085L; [CONTEXT]   public abstract class ValuedEnum extends Enum {  [BUGGY] private static final short serialVersionUID = -7129650521543789085L; [BUGGY]     private final int iValue;  [CLASS] ValuedEnum  [VARIABLES] '
    groundTruth = '[PATCH] '+groundTruth.replace('\t',' ').replace('\n',' ').replace('\r',' ').replace('  ',' ')
    
    print("*****sample**** :"+sample)


    with open(repodir+'/train-'+bugId+'.csv','a')  as csvfile:
        filewriter = csv.writer(csvfile, delimiter='\t',  escapechar=' ',   #delimiter='\t'表示用tab分隔，escapechar=' '表示用空格转义，quoting=csv.QUOTE_NONE表示不用引号，通常字段有特殊字符如逗号或新行等就会被括号括起来
                                quoting=csv.QUOTE_NONE)               
        filewriter.writerow([groundTruth,sample,action])  #上下文中包含了buggy line 




def diagnostic(bugId,line,targetfile,repodir,action,executeFlag,rootdir):
    project = bugId.split('-')[0]
    line=line.replace('\r',' ').replace('\n',' ')
    filename = targetfile.split('/')[-1]
    originFile = targetfile.replace("Perturbation-","")
    print("*****originFile originFile**** :"+originFile)
    print("*****diagnostics**** :")


    #copy the origin file outside the project，之后这个文件会被覆盖，所以要先复制一份
    os.system("cp "+originFile+"  "+repodir)
    # initial perturb string
    perturbStr=''
    
    print("target line:"+line)
    infos = line.split('^')
    curruptCode =  infos[1]  
    lineNo1 =  infos[2] 
    lineNo2 =  infos[3] 
    lineNo3 =  infos[4] 
    lineNo4 =  infos[5]
    lineNo5 =  infos[6]

    print('**************Currupt Code*************'+curruptCode)
    
    
    if "Transplant" in action or "Replace" in action or "Move" in action or  "Insert" in action:
        # read and perturb code 
        with open(originFile,'r') as perturbFile:
            lines = perturbFile.readlines()
            for i in range(0,len(lines)):
                if i+1< int(lineNo1) or i+1> int(lineNo1)+4:
                    perturbStr+=lines[i]
                elif i+1==int(lineNo1):
                    perturbStr+=curruptCode+"\n"
                elif i+1==int(lineNo1)+1: 
                    if lineNo2=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+2:
                    if lineNo3=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+3:  
                    if lineNo4=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+4:
                    if lineNo5=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
    #REMOVE actions
    elif "P14_" in action or 'P15_' in action or 'P16_' in action:
        with open(originFile,'r') as perturbFile:
            lines = perturbFile.readlines()
            for i in range(0,len(lines)):
                if i+1< int(lineNo1) or i+1> int(lineNo1)+4:
                    perturbStr+=lines[i]
                elif i+1==int(lineNo1):
                    perturbStr+= curruptCode
                elif i+1==int(lineNo1)+1: 
                    if lineNo2=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+2:
                    if lineNo3=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+3:  
                    if lineNo4=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"
                elif i+1==int(lineNo1)+4:
                    if lineNo5=='':
                        perturbStr+=lines[i]
                    else:
                        perturbStr+=" \n"


    # 不同的扰动规则对应不同的扰动代码。为什么要将扰动代码写回到扰动前的文件中？因为扰动前的文件中包含了buggy line，而扰动后的文件中没有buggy line，可是这样扰动前的文件会被覆盖，怎么办？因为扰动前的文件已经被复制到了Samples_SelfAPR文件夹下，所以不用担心
    # write back the perturb code to class file
    with open(originFile,'w') as perturbFileWrite:
        perturbFileWrite.write(perturbStr)
    #获取诊断信息，在扰动前的文件中使用compile进行编译（注意此时扰动前的文件包含了扰动代码及其上下文），如果编译成功，就使用test进行测试，如果测试成功，就返回[NO-ERROR]，如果测试失败，就返回[FE]，如果编译失败，就返回[CE]
    if executeFlag:
        execute_result = executePerturbation(bugId,repodir,originFile,action,line,rootdir)
    else:
        execute_result=''
    
    return execute_result




def executePerturbation(bugId,repodir,originFile,action,line,rootdir):
    bugId = bugId.replace('Perturbation-','')
    compile_error_flag = True

    program_path=repodir+'/'+bugId
    print('****************'+program_path+'******************')
    #get compile result
    cmd = "cd " + program_path + ";"
    cmd += "timeout 90 defects4j compile"
    exectresult='[TIMEOUT]'
    symbolVaraible=''
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    print(result)
    # Running ant (compile.tests)
    if 'Running ant (compile)' in str(result):
        result = str(result).split("Running ant (compile)")[1]
        print('===result==='+str(result))

        result=result.split('\n')
        for i in range(0,len(result)):
            if 'error: ' in result[i]:
                firstError=result[i].split('error: ')[1]
                exectresult=firstError.split('[javac]')[0]
                if '\\' in exectresult:
                    exectresult=exectresult.split('\\')[0]
                print('===FirstError==='+firstError)
                # 'cannot  find  symbol      
                if 'symbol' in firstError and 'cannot' in firstError and 'find' in firstError:       
                    if '[javac]' in firstError:
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
                exectresult='[FE]'
                compile_error_flag=False



    if not compile_error_flag:
        #get test result
        cmd = "cd " + program_path + ";"
        cmd += "timeout 180 defects4j test"
        result=''
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        print(result)
        if 'Failing tests: 0' in str(result):
            exectresult='[NO-ERROR]'
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

    with open(repodir+'/diagnostic.csv','a')  as csvfile:
        filewriter = csv.writer(csvfile, delimiter='\t',  escapechar=' ', 
                                quoting=csv.QUOTE_NONE)               
        filewriter.writerow([exectresult,line])

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




def getFailingTestSourceCode(failingtest,program_path):
    code=''
    if os.path.exists((program_path+'/tests')):
        program_path = program_path+'/tests/'
    elif os.path.exists(program_path+'/test'):
        program_path = program_path+'/test/'
    elif os.path.exists(program_path+'/src/test/java'):
        program_path = program_path+'/src/test/java/'
    elif os.path.exists(program_path+'/src/test'):
        program_path = program_path+'/src/test/'
    elif os.path.exists(program_path+'/gson/src/test/java'):
        program_path = program_path+'/gson/src/test/java/'

    print(failingtest+'&&&&&&&&failingtest')
    testclass = failingtest.split("::")[0]
    testmethod = failingtest.split("::")[1]
    testclass=testclass.replace('.','/')
    testclass = testclass+'.java'

    fullpath = program_path+testclass

    if os.path.exists(fullpath):    
        startflag=False
        code =''
        with open(fullpath,'r') as codefile:
            lines=codefile.readlines()
            for l in lines:
                if 'public' in l  and 'void' in l and testmethod in l:
                    startflag=True
                if 'public' in l and 'void' in l and testmethod not in l:
                    startflag=False
                if startflag:
                    if 'assert' in l:
                        l = l.strip()
                        if l not in code:
                            code=l
    return code








if __name__ == '__main__':
    bugIds = ['Lang-65','Chart-26','Math-106','Mockito-38','Time-26','Closure-134','Cli-1','Collections-25','Codec-1','Compress-1','Csv-1','Gson-1','JacksonCore-1','JacksonDatabind-1','JacksonXml-1','Jsoup-1','JxPath-1'] 
    #bugIds = ['Jsoup-1','JxPath-1'] 
    rootdir= '/home/sunwanqi/caowy/APR/SelfAPR'
    repodir = rootdir+'/Samples_SelfAPR'

    for bugId in bugIds:
        project=bugId.split('-')[0]
        bugNo = bugId.split('-')[1]

        if os.path.exists(repodir+'/'+bugId):
            os.system('rm -rf '+repodir+'/'+bugId)   #判断扰动前的文件是否存在，存在就删除
        os.system('defects4j checkout -p '+ str(project)+' -v '+str(bugNo)+'f   -w '+repodir+'/'+bugId)
        #将扰动前的fix项目文件下载至Samples_SelfAPR文件夹下
        bugId = bugId.replace(project, "Perturbation-"+project)
        start(bugId,repodir,rootdir)
