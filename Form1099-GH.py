from dateutil.parser import parse
from selenium import webdriver
import json, time, math

from PyPDF2 import PdfFileWriter, PdfFileReader
from PyPDF2.generic import BooleanObject, NameObject, IndirectObject

def set_need_appearances_writer(writer: PdfFileWriter):
    # See 12.7.2 and 7.7.2 for more information: http://www.adobe.com/content/dam/acom/en/devnet/acrobat/pdfs/PDF32000_2008.pdf
    try:
        catalog = writer._root_object
        # get the AcroForm tree
        if "/AcroForm" not in catalog:
            writer._root_object.update({
                NameObject("/AcroForm"): IndirectObject(len(writer._objects), 0, writer)})

        need_appearances = NameObject("/NeedAppearances")
        writer._root_object["/AcroForm"][need_appearances] = BooleanObject(True)
        return writer

    except Exception as e:
        print('set_need_appearances_writer() catch : ', repr(e))
        return writer


def readPDFwApp(infile):
    read_pdf = PdfFileReader(open(infile, "rb"), strict=False)
    if "/AcroForm" in read_pdf.trailer["/Root"]:
        read_pdf.trailer["/Root"]["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)})
    return read_pdf


def writePDFwApp():
    write_pdf = PdfFileWriter()
    set_need_appearances_writer(write_pdf)
    if "/AcroForm" in write_pdf._root_object:
        write_pdf._root_object["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)})
    return write_pdf


class Form1099(object):
    # ['Desc', 'CUSIP', 'Qty', 'Date Acq', 'Date Disc', 'Proceeds', 'Cost Basis', 'Adj Code', 'Adj Amt', 'Gain/Loss']
    # Attribute:
    #   self.__string_list -> List of lists for each transaction in above format
    def __init__(self, i_txt):
        self.__string_list = []
        try:
            try:
                self.__importRH1099(i_txt)
                self.source = 'Robinhood Clearing'
            except:
                self.__importApex1099(i_txt)
                self.source = 'Apex Clearing'
        except:
            exit(-3)

    def __importRH1099(self, i_txt):
        try:
            # Open, read, store lines in a list, then close the input .txt file
            textRH = open(i_txt, 'rb')
            in_list = textRH.readlines()
            textRH.close()

            # Strings used to turn on/off recording relevant line data in for loop below
            # -> Probably not optimal
            start_strs = ['(Z) Additional information']
            end_strs = ['* This is important tax information', 'Tax lot closed on a first in']
            del_strs = ['Option written', 'also not reported', 'Security total', 'Page ', 'x0c', 'Total of']

            # Initialize record boolean and output list from first data scrape
            rec_line = False
            out_list = []

            for line in in_list:
                # First line below deals with leading and trailing special characters
                # -> Probably not the best way to handle this, could cause issues if formatting/encoding differs?
                read_line = str(line)[2:-5]
                if any(string in read_line for string in end_strs):
                    rec_line = False
                if rec_line and not any(string in read_line for string in del_strs):
                    out_list.append(read_line + '\n')
                if any(string in read_line for string in start_strs):
                    rec_line = True

            if out_list == []:
                exit(-1)

            out_list = [line.replace(',', '') for line in out_list]

            desc = ""
            date_dis = ""

            self.__string_list = []

            for line in out_list:
                # 'CUSIP:' only shows up in lines signaling the start of a block of transactions
                # -> Get security name and store for use until end of block
                if 'CUSIP:' in line:
                    desc = line.split(' / ')
                    desc = desc[0]
                # ''transactions for' shows up in lines signaling multiple positions discharged on a given day
                # -> Get date and store for use until end of sub-block
                elif 'transactions for' in line:
                    line_split = line.split(' transactions for ')
                    date_dis = line_split[1].split('.')[0]
                else:
                    r = line.split()
                    try:
                        #
                        float(r[0])
                        row_out = [desc, '', r[0], r[2][:6] + '20' + r[2][6:], date_dis[:6] + '20' + date_dis[6:], r[1], r[3]]
                        if r[5] == 'W':
                            row_ext = [r[5], r[4], r[6]]
                        else:
                            row_ext = ['', '0.00', r[5]]
                        row_out.extend(row_ext)
                    except:
                        try:
                            parse(r[0])
                            row_out = [desc, '', r[1], r[3][:6] + '20' + r[3][6:], r[0][:6] + '20' + r[0][6:], r[2], r[4]]
                            if r[6] == 'W':
                                row_ext = [r[6], r[5], r[7]]
                            else:
                                row_ext = ['', '0.00', r[6]]
                            row_out.extend(row_ext)
                        except:
                            row_out = []
                    if row_out != []:
                        self.__string_list.append(row_out)

        except:
            print('Unable to initialize instance.')
            exit(-1)

    def __importApex1099(self, i_txt):
        try:
            # Open, read, store lines in a list, then close the input .txt file
            textApex = open(i_txt, 'rb')
            in_list = textApex.readlines()
            textApex.close()

            # Strings used to turn on/off recording relevant line data in for loop below
            # -> Probably not optimal
            start_strs = ['(Box 1f)']
            end_strs = ['THIS IS YOUR FORM 1099 (COPY B FOR RECIPIENT)', 'ITEMS - TOTAL']
            del_strs = ['Subtotals']

            # Initialize record boolean and output list from first data scrape
            rec_line = False
            out_list = []

            for line in in_list:
                # First line below deals with leading and trailing special characters
                # -> Probably not the best way to handle this, could cause issues if formatting/encoding differs?
                read_line = str(line)[2:-5]
                if any(string in read_line for string in end_strs):
                    rec_line = False
                if rec_line and not any(string in read_line for string in del_strs):
                    out_list.append(read_line)
                if any(string in read_line for string in start_strs):
                    rec_line = True

            if out_list == []:
                exit(-2)

            del_strs = ['\n', ')', '$']

            out_list = [line.replace('$', '') for line in out_list]
            out_list = [line.replace(')', '') for line in out_list]
            out_list = [line.replace('(', '-') for line in out_list]
            out_list = [line.replace(',', '') for line in out_list]

            last_out = ''
            desc = ''
            cusip = ''

            self.__string_list = []

            for line in out_list:
                out_sp = line.split()
                try:
                    float(out_sp[0])
                    adj_code = ''
                    if out_sp[6] != '0.00':
                        adj_code = 'W'
                    self.__string_list.append([desc, cusip, out_sp[0], out_sp[1], out_sp[2], out_sp[3], out_sp[4], adj_code, out_sp[6], out_sp[7]])
                except:
                    if out_sp[0] == 'CUSIP:':
                        cusip = out_sp[1]
                        desc = str(last_out)[0:-1]
                        last_out = ''
                    else:
                        last_out += line
        except:
            print('Unable to initialize instance.')
            exit(-2)

    def numTransactions(self, desc = None):
        if desc == None:
            return len(self.__string_list)
        else:
            i = 0
            for row in self.__string_list:
                if desc in row:
                    i += 1
            return i

    def listTransactions(self, desc = None):
        if desc == None:
            return self.__string_list
        else:
            listTrans = []
            for row in self.__string_list:
                if desc in row:
                    listTrans.append(row)
            return listTrans

    def sumTransactions(self, desc = None):
        proc = 0.00
        basis = 0.00
        adj = 0.00
        gainloss = 0.00
        for row in self.__string_list:
            if desc == None or desc in row:
                proc += float(row[5].replace(',', ''))
                basis += float(row[6].replace(',', ''))
                adj += float(row[8].replace(',', ''))
                gainloss += float(row[9].replace(',', ''))
        return [round(proc, 2), round(basis, 2), round(adj, 2), round(gainloss, 2)]

    def listDescriptions(self, desc = None):
        listDesc = []
        for row in self.__string_list:
            if desc == None or desc in row[0]:
                if row[0] not in listDesc:
                    listDesc.append(row[0])
        return listDesc

    def listAdjTrans(self):
        listAdjTrans = []
        for row in self.__string_list:
            if row[7] == 'W':
                listAdjTrans.append(row)
        return listAdjTrans

    def listNonAdjTotals(self):
        listNonAdj = [0.00, 0.00]
        for row in self.__string_list:
            if row[7] != 'W':
                for i in range(0, 2):
                    listNonAdj[i] += float(row[5 + i])
        return listNonAdj

    def listAdjTotals(self):
        listAdj = [0.00, 0.00, 0.00]
        for row in self.__string_list:
            if row[7] == 'W':
                for i in range(0, 2):
                    listAdj[i] += float(row[5 + i])
                listAdj[2] += float(row[8])
        return listAdj

    def getCKnonAdjAgg(self):
        nonAdjAgg = ['1', self.source, 'Various', '12/31/2018', 0.00, 0.00, '', '0.00']
        for row in self.__string_list:
            if row[7] == '':
                for col in range(0, 2):
                    nonAdjAgg[4 + col] += float(row[5 + col])
        for i in range(0, 2):
            nonAdjAgg[i + 4] = str(nonAdjAgg[i + 4])
        return nonAdjAgg

    def getCKAdjTrans(self):
        AdjTrans = []
        for row in self.__string_list:
            if row[7] == 'W':
                if float(row[5]) < 0:
                    pass
                else:
                    AdjTrans.append(['1', row[0] + '; QTY: ' + row[2], row[3], row[4], row[5], row[6], row[7], row[8]])
        return AdjTrans

    def getAdjTransSubs(self):
        AdjTr = self.listAdjTrans()
        ldesc = ''
        ldate = ''
        desc = ''
        date = ''
        subt = ['', '', '', ]
        AdjTrSub = []
        for i in range(len(AdjTr)):
            desc = AdjTr[i][0] + '; CUSIP: ' + AdjTr[i][1] + '; QTY: ' + AdjTr[i][2]
            date = AdjTr[4]

    def processList(self):
        NonAdjTrans = []
        RegAdjTrans = []
        NegProcTrans = []
        for row in self.__string_list:
            if row[7] != 'W':
                NonAdjTrans.append(row)
            elif float(row[5]) < 0:
                NegProcTrans.append(row)
            else:
                RegAdjTrans.append(row)
        return [NonAdjTrans, RegAdjTrans, NegProcTrans]


def addStrs(s1, s2):
    return str(float(s1) + float(s2))

def SumFormList(formList):
    i = 0
    total = ['Transactions: ', '', '', '', '', '0.00', '0.00', '', '0.00', '0.00']
    for row in formList:
        try:
            total[5] = addStrs(total[5], row[5])
            total[6] = addStrs(total[6], row[6])
            total[8] = addStrs(total[8], row[8])
            total[9] = addStrs(total[9], row[9])
            i += 1
        except:
            print('ERROR')
    total[0] = total[0] + str(i)
    return total

def getSubtotalList(formList):
    subList = []
    lrow = ['', '', '0.0', '', '', '0.00', '0.00', '', '0.00', '0.00']
    for row in formList:
        try:
            if row[0] == lrow[0] and row[4] == lrow[4]:
                lrow = [row[0], row[1], addStrs(row[2], lrow[2]), 'VARIOUS', row[4], addStrs(row[5], lrow[5]), addStrs(row[6], lrow[6]), '', addStrs(row[8], lrow[8]), addStrs(row[9], lrow[9])]
                if float(lrow[8]) > 0:
                    lrow[7] = 'W'
            else:
                subList.append(lrow)
                lrow = row
        except:
            print('ERROR')
    del subList[0]
    return subList


rh1099 = Form1099('1099-RH.txt')
apex1099 = Form1099('1099-Apex-RH.txt')

rhTrans = rh1099.processList()

for i in range(3):
    print(SumFormList(rhTrans[i]))

apexTrans = apex1099.processList()
for i in range(3):
    print(SumFormList(apexTrans[i]))

print(SumFormList(rhTrans[0]))
print(SumFormList(apexTrans[0]))

rhNAdAgg = SumFormList(rhTrans[0])
apNAdAgg = SumFormList(apexTrans[0])

for row in rhTrans[2]:
    print(row)
print(SumFormList(rhTrans[2]))



CapGains = []
CapGains.append(['1', 'APEX CLEARING NONADJUSTED AGGREGATE', 'VARIOUS', '12/31/2018', apNAdAgg[5], apNAdAgg[6], apNAdAgg[7], apNAdAgg[8]])
CapGains.append(['1', 'ROBINHOOD CLEARING NONADJUSTED AGGREGATE', 'VARIOUS', '12/31/2018', rhNAdAgg[5], rhNAdAgg[6], rhNAdAgg[7], rhNAdAgg[8]])
for row in rhTrans[1]:
    CapGains.append(['1', row[0] + '; QTY: ' + row[2], row[3], row[4], row[5], row[6], row[7], row[8]])
for row in apexTrans[1]:
    CapGains.append(['1', row[0] + '; QTY: ' + row[2], row[3], row[4], row[5], row[6], row[7], row[8]])


with open('cookie2.txt', 'rb') as cookie_file:
    cookie_load = json.loads(cookie_file.read())
cookies = []
for cookie in cookie_load:
    cookies.append({key:cookie[key] for key in ['name', 'value', 'path', 'domain', 'secure']})

driver = webdriver.Firefox()
driver.get('http://tax.creditkarma.com')
for cookie in cookies:
    try:
        driver.add_cookie(cookie)
    except:
        print(" FAIL!")
driver.execute_script("window.localStorage.setItem(arguments[0], arguments[1]);", "CKPERSISTID", "VALUE")  #Update this for your browser

for i in range(0, 2):
    driver.execute_script('arguments[0].value = "YOUR USERNAME"', driver.find_element_by_id('username'))
    driver.execute_script('arguments[0].value = "YOUR PASSWORD"', driver.find_element_by_id('password'))
    driver.execute_script('arguments[0].click();', driver.find_element_by_id('Logon'))
    time.sleep(5)

driver.get('https://tax.creditkarma.com/taxes/CapitalGainsFullListSummary.action')

for i in range(0, int(len(CapGains)/10)):
    driver.execute_script('arguments[0].click();', driver.find_element_by_id('addRows'))

colCats = ['reported', 'description', 'dateAcquired', 'dateSold', 'salesPrice', 'cost', 'adjustmentCode', 'adjustmentAmount']
webTable = driver.find_elements_by_tag_name('Table')[0]
capitalGainsTable = driver.find_elements_by_tag_name('Table')[1]

TableCols = []
for col in colCats:
    TableCols.append(capitalGainsTable.find_elements_by_class_name(col))

Table = [TableCols[0]]
for i in range(1, len(TableCols)):
    Table.append(TableCols[i][1::])

clear = ['0', '', '', '', '0.00', '0.00', '', '0.00']
for i in range(0, len(Table[0])):
    for j in range(0, len(Table)):
        driver.execute_script('arguments[0].value = "' + clear[j] + '"', Table[j][i])

for i in range(0, len(CapGains)):
    for j in range(0, len(CapGains[0])):
        driver.execute_script('arguments[0].value = "' + str(CapGains[i][j]) + '"', Table[j][i])

infile = "f8949.pdf"

pdf = PdfFileReader(open(infile, "rb"), strict=False)
pfields = pdf.getFormTextFields()
pfvalues = pfields.values()

if "/AcroForm" in pdf.trailer["/Root"]:
    pdf.trailer["/Root"]["/AcroForm"].update(
        {NameObject("/NeedAppearances"): BooleanObject(True)})

i = 0
for key in pfields:
    pfields[key] = str(i)
    i += 1

# 0 is name, 1 is SSN
# need to precheck Box A
# 2 to 113; 14 rows, 8 columns
# 114 is tproc, 115: tcost, 116: dont use, 117: adj total, 118 gain/loss total

pgs = math.floor(len(rhTrans[2])/14) + 1
print(pgs)

dic = {}
pgkeys = []
allvals = []

for i in range(3, 115):
    pgkeys.append("f1_" + str(i)+ "[0]")

for row in rhTrans[2]:
    allvals.append(row[0] + '; QTY: ' + row[2])
    for j in range(3, 10):
        allvals.append(row[j])

for j in range(pgs):

    outfile = "f8949_out_" + str(j) + ".pdf"

    pdf2 = PdfFileWriter()
    set_need_appearances_writer(pdf2)
    if "/AcroForm" in pdf2._root_object:
        pdf2._root_object["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)})

    f = dict(zip(pgkeys, allvals[112*j:112*(j + 1)]))
    print((rhTrans[2][14*j:14*(j+1)]))
    print(SumFormList(rhTrans[2][14*j:14*(j+1)]))
    pdf2.addPage(pdf.getPage(0))
    pdf2.updatePageFormFieldValues(pdf2.getPage(0), f)

    outputStream = open(outfile, "wb")
    pdf2.write(outputStream)


