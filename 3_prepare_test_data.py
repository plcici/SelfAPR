#!/usr/bin/python
import sys, os, time, subprocess,fnmatch, shutil, csv,re, datetime
#在SelfAPR文件夹下下载每个项目的每个版本，如Chart-1，对于每个项目，从D4JMeta.csv获取对应的java文件名、从D4JDiff文件获取对应的buggy line等信息
#D4JMeta.csv——#'source/org/jfree/chart/renderer/category/AbstractCategoryItemRenderer.java'
#D4JDiff——#'73[buggy]if (raw == String.class || raw == Object.class) { [patch]if (raw == String.class || raw == Object.class || raw == CharSequence.class) { [buggyLineNo]1'
#TODO:D4JMeta.csv文件和D4JDiff文件内容；难道不应该是获取训练数据时获取这些测试诊断信息？》？？

def start(bugId,repodir,rootdir):
    projectPath=repodir+'/'+bugId  #'/home/sunwanqi/caowy/APR/SelfAPR//Chart_2'
    #get buggy file and buggy line
    print('bugid'+bugId)

    targetfile = getBuggyFile(bugId,repodir)  #每个java文件，repodir='/home/sunwanqi/caowy/APR/SelfAPR/'
    print('target......'+targetfile)
    if ',' in targetfile:   #如果此项目有多个java文件
        return
    
    tfiles = targetfile.split(',')     #多个targetfile的情况
    firstTFile=targetfile.split(',')[0]

    for tf in tfiles:
        if '.java' not in tf:
            tf=tf+'.java'
        diffLists = getBuggyLines(bugId,repodir,tf)
        print('======diffLists========='+str(diffLists))  #diffLists是每个java文件的buggy及hunk信息，可能有多次的删除和添加
        
        if len(diffLists)>1:
            return;  #TODO:diffLists为什么大于1时会return，我猜可能是忽略一个项目中有多个修复的场景
        
        for k in range(0,len(diffLists)):
            diff=diffLists[k]
            startLineNo=diff.split('[buggy]')[0]
            buggyLines=diff.split('[buggy]')[1]
            buggyLines=buggyLines.split('[patch]')[0]
            patchLines = diff.split('[patch]')[1]
            patchLines = patchLines.split('[buggyLineNo]')[0]
            buggyLineCount = diff.split('[buggyLineNo]')[1]
        

            if str(startLineNo) not in '':
                constructTestSample(bugId, k, tf, repodir, rootdir,str(startLineNo),buggyLines,patchLines,str(len(diffLists)),str(buggyLineCount))
   
    if os.path.exists(repodir+'/'+bugId):
        os.system('rm -rf '+repodir+'/'+bugId)

def getBuggyFile(bugId,repodir):
    #get buggy file
    diffDir = repodir+'scripts/D4JMeta.csv'  
    bugIdUnderScore = bugId.replace('-','_')
    targetFile = ''
    with open(diffDir,'r') as meta:
        lines = meta.readlines()
        for l in lines:
            if '\t' in l:
                bid = l.split('\t')[1]
                if bugIdUnderScore in bid and bid in bugIdUnderScore:           
                    targetFile = l.split('\t')[2]   
                    break
    return targetFile   #'source/org/jfree/chart/renderer/category/AbstractCategoryItemRenderer.java'

def getBuggyLines(bugId,repodir,tf):
    tclass=tf.split('/')[-1]
    tclass=tclass.replace('.java','').replace('\n',' ').replace('\r',' ')
    print(tclass)
    projectPath=repodir+repodir
    #tdiff = repodir+'scripts/D4JDiff/'+bugId+'_'+tclass+'.diff'   #tdiff是对每个项目的不同编号下的.java项目进行的diff操作，'/home/sunwanqi/caowy/APR/SelfAPR/scripts/D4JDiff/Chart_1_AbstractCategoryItemRenderer.diff'
    tdiff = '/home/sunwanqi/caowy/APR/SelfAPR/scripts/HumanBearsPatch/Bears-2.diff'
    diffList=[]
    with open(tdiff,'r', encoding='latin1') as diff:
        lines = diff.readlines()
        hunks = str(lines).split('@@ -')   #"@@ -72,7 +72,7 @@ public class StdKeyDeserializer extends KeyDeserializer".split('@@ -')的结果为['', '72,7 +72,7 @@ public...serializer']
        for i in range(1,len(hunks)):    #[ '72,7 +72,7 @@ public...serializer']如果是buggy line
            h = hunks[i]
            startLineNo=''
            buggyLines=''
            patchLines=''
            buggyLineNo=0
            print('*********hunk hunk hunk***********'+h)
            lines = h.split("\\n', '")     #将string转换为list
            for l in lines:
                if '@@' in l and '+' in l and ',' in l:
                    startLineNo= l.split(',')[0]
                    startLineNo= str(int(startLineNo)+1)   
                
                if l.startswith('-'):
                    startword = l[1:]   #去掉减号
                    startword = startword.replace("\\n', \"+ ",' ')
                    startword = startword.replace("\\n\", '",' ')
                    startword =  startword.strip()
                    if not startword.startswith('/') and not startword.startswith('*') and not startword.startswith('import') and not startword.startswith('System.out') and not startword.startswith('Logger') and not startword.startswith('log.info') and  not startword.startswith('logger')  and  not startword.startswith('//'):
                        startword = startword.split('//')[0]
                        print('*********buggyLines buggyLines***********'+startword)
                        buggyLines = buggyLines + startword+' '
                                               
                        buggyLineNo+=1
                                      
                if l.startswith('+'):
                    startword = l[1:]
                    startword =  startword.strip()
                    if not startword.startswith('/') and not startword.startswith('*') and not startword.startswith('import') and not startword.startswith('System.out') and not startword.startswith('Logger') and not startword.startswith('log.info') and  not startword.startswith('logger') and  not startword.startswith('//'):
                        startword = startword.split('//')[0]
                        startword = startword.replace("\\n', \"+ ",' ')
                        print('*********patchLines patchLines***********'+startword)

                        patchLines = patchLines + startword+' '

            #'73[buggy]if (raw == String.class || raw == Object.class) { [patch]if (raw == String.class || raw == Object.class || raw == CharSequence.class) { [buggyLineNo]1'
            hunkinfo = startLineNo+'[buggy]'+buggyLines+'[patch]'+patchLines+'[buggyLineNo]'+str(buggyLineNo)
            diffList.append(hunkinfo)   #每个java文件的buggy及hunk信息
    print(str(diffList))
    return diffList

#indexId是diffLists的第n个、totalhunk是diffLists的总数量、bno是buggyLineNo
def constructTestSample(bugId, indexId, targetfile, repodir, rootdir,startLineNo,buggyLines,patchLines,totalhunk,bno):   
    origTargetFile=targetfile.replace('\r','').replace('\n','')
    className = targetfile.split('/')[-1]
    className = className.replace('.java','').replace('\r','').replace('\n','')
    targetfile=repodir+bugId+'/'+targetfile
    targetfile = targetfile.split('.java')[0]+'.java'
    targetfile=targetfile.replace('\r','').replace('\n','')
    print('targetfile'+targetfile)
    print('startLineNo=========startLineNo====='+startLineNo)
    print('bugId=========bugId====='+bugId)
    print('buggyLines'+buggyLines)
    cxt=''
    metaInfo=''
    diagnosticMsg = executePerturbation(bugId,repodir,rootdir)
    print(diagnosticMsg)


    cmd = 'timeout 200 java -jar /home/sunwanqi/caowy/APR/SelfAPR/perturbation_model/target/perturbation-0.0.1-SNAPSHOT-jar-with-dependencies.jar '+targetfile+' test-'+startLineNo 
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    print(result)
    result = str(result)
    if '[CLASS]' in result:
        metaInfo = result.split('[CLASS]')[-1]
    if 'startline:' in result:
        cxtStart=result.split('startline:')[1]
        cxtStart=cxtStart.split(' ')[0]
    else:
        cxtStart = int(startLineNo)-10
    if 'endline:' in result:
        cxtEnd=result.split('endline:')[1]
        if '\'' in cxtEnd:
            cxtEnd=cxtEnd.split('\'')[0]
        if '\"' in cxtEnd:
            cxtEnd=cxtEnd.split('\"')[0]
    else:
        cxtEnd=int(startLineNo)+10


    print('meta=========meta====='+metaInfo)
    
    if 'startline' in metaInfo:
        metaInfo = metaInfo.split('startline')[0]
        

        
    if (int(cxtEnd) - int(startLineNo))>10:
        cxtEnd = str(int(startLineNo)+10)
    if (int(startLineNo) - int(cxtStart))>10:
        cxtStart = str(int(startLineNo)-10)       
    cxtStart=str(cxtStart)
    cxtEnd=str(cxtEnd)
      
    print('cxtStart=========cxtStart====='+cxtStart)
    print('cxtEnd=========cxtEnd====='+cxtEnd)

    sample=''
    #get context info
    if cxtStart not in '' and cxtEnd not in '':
        with open(targetfile,'r',encoding='latin1') as perturbFile:
            lines = perturbFile.readlines()
            for i in range(0,len(lines)):
                if i > int(cxtStart)-2 and i < int(cxtEnd):
                    l = lines[i]
                    l = l.strip()
                    #remove comments
                    if  l.startswith('/') or l.startswith('*'):
                        l = ' '
                    l = l.replace('  ','').replace('\r','').replace('\n','')
                    l = l.split('// ')[0]
                    if int(bno) > 0:
                        if i == int(startLineNo)-1:
                            l=' [BUGGY] '+l
                        elif i == int(startLineNo)+ int(bno) -1:   #TODO:比如StartLine是73，那么72、72都要标注[BUGGY],why??确保前后都有嘛？
                            l= ' [BUGGY] '+l
                    elif int(bno) == 0:   #TODO:buggylineNo为0？？？
                        if i == int(startLineNo)-1:
                            l=' [BUGGY] [BUGGY] '+l
      
                    cxt+=l+' '

    
    sample+='[BUG] [BUGGY] ' + buggyLines +' '+ diagnosticMsg+' '+' [CONTEXT] ' + cxt + ' [CLASS]  '+ metaInfo

    sample = sample.replace('\r','').replace('\n','').replace('\t','')
    sample = sample.replace('  ',' ')
    print(sample)

    global countindex 
    with open(repodir+'/test.csv','a')  as csvfile:
        filewriter = csv.writer(csvfile, delimiter='\t',  escapechar=' ', 
                                quoting=csv.QUOTE_NONE)               
        filewriter.writerow([str(countindex),'[PATCH] '+patchLines,sample,bugId+'_'+className+'_'+totalhunk+'_'+str(int(indexId)+1),startLineNo,str(bno),origTargetFile])
        countindex+=1




#获取测试诊断信息
def executePerturbation(bugId,repodir,rootdir):
    compile_error_flag = True
    project = bugId.split('_')[0]
    bugNo = bugId.split('_')[1]
    exectresult=''
    program_path=repodir+'/'+bugId
    print('****************'+program_path+'******************')
   
    #get test result
    cmd = "cd " + program_path + ";"
    cmd += "defects4j info -p "+project +"  -b "+bugNo
    result=''
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)  #Get information for a specific bug (commons lang, bug 1)
    print(result)
    failingtest = ''
    faildiag = ''
    if 'Root cause in triggering tests:' in str(result):
        result=str(result).split('Root cause in triggering tests:')[1]
    if '--------' in str(result):
        result=str(result).split('--------')[0]  #获取详细具体的错误信息，'\\n - org.jfree.chart.renderer.category.junit.AbstractCategoryItemRendererTests::test2947660\\n   --> junit.framework.AssertionFailedError: expected:<1> but was:<0>\\n'
    print(result)
    resultLines = str(result).split('\\')  #['', 'n - org.jfree.chart.renderer.category.junit.AbstractCategoryItemRendererTests::test2947660', 'n   --> junit.framework.AssertionFailedError: expected:<1> but was:<0>', 'n']
    for l in resultLines:
        if '-' in l and '::' in l and failingtest  in '':
            failingtest = l.split('-')[1]
            failingtest=failingtest.strip()  #org.jfree.chart.renderer.category.junit.AbstractCategoryItemRendererTests::test2947660
        if '-->' in l and faildiag  in '':
            faildiag = l.split('-->')[1]
            if '.' in faildiag:
                faildiag_dots = faildiag.split('.')
                if len(faildiag_dots)>2:
                    faildiag=''
                    for i in range(2,len(faildiag_dots)):
                        faildiag+=faildiag_dots[i]  #'AssertionFailedError: expected:<1> but was:<0>'
  
    print('==========failingtest======='+failingtest)
    print('==========faildiag======='+faildiag)

    failingTestMethod=failingtest.split('::')[1]  #'test2947660'
    exectresult = '[FE] ' + faildiag +' '+failingTestMethod  #'[FE] AssertionFailedError: expected:<1> but was:<0> test2947660'
    os.chdir(rootdir)

    return exectresult



if __name__ == '__main__':

    global countindex
    countindex=497

    #bugIds = ['Chart-26','Math-106','Lang-65','Cli-1','Closure-134','Codec-1','Mockito-38','Jsoup-1','JacksonDatabind-1','JacksonCore-1','Compress-1','Collections-25','Time-26','JacksonXml-1','Gson-1','Csv-1','JxPath-1']   
    #bugNos = ['1-25','1-105','1-64','2-40','1-170','2-18','1-37','2-93','2-112','2-26','2-47','26-28','1-27','2-6','2-18','2-16','2-22',]
    bugIds = ['Chart-26','JacksonXml-1']
    bugNos = ['1-25','2-6']
    #TODO:bugNos是项目的其他版本，那么这些顺序是按照什么挑选出来的
    rootdir= '/home/sunwanqi/caowy/APR/SelfAPR'
    repodir = rootdir+'/'

    for i in range(0,len(bugIds)):
        proj=bugIds[i]
        project=proj.split('-')[0]
        bugNo = bugNos[i]
        rangeStart = bugNo.split('-')[0]
        rangeEnd = bugNo.split('-')[1]
        # int(rangeStart) int(rangeEnd)+1
        for i in range(int(rangeStart), int(rangeEnd)+1):   #Chart-26举例，i=1-26
            bugId = project+'_'+str(i)  #bugId=Chart_1
            if os.path.exists(repodir+'/'+bugId):   
                os.system('rm -rf '+repodir+'/'+bugId)
            os.system('rm -rf '+repodir+'/'+project+'*')  
            try:
                os.system('defects4j checkout -p '+ str(project)+' -v '+str(i)+'b   -w '+repodir+'/'+bugId)
                start(bugId,repodir,rootdir)
            except (RuntimeError, TypeError, NameError,FileNotFoundError):
                print(RuntimeError)
