# -*- coding: utf-8 -*-
"""
 @desc:
 @author: zengls
 @software: PyCharm on 2018-8-12
"""
import requests
from lxml import etree
import json
from fake_useragent import UserAgent
import pymongo
from time import sleep,time
import random
import pandas as pd
from enum import Enum

#定义字段枚举类，用于设定目标抓取的字段
class Field(Enum):
    companyId = '公司ID'
    positionId = '岗位ID'
    jobNature = '工作性质'
    financeStage = '发展阶段'
    companyName = '公司简称'
    companyFullName = '公司全称'
    companySize = '公司规模'
    industryField = '领域'
    positionName = '岗位名称'
    city = '工作城市'
    createTime = '发布时间'
    salary = '工资'
    workYear = '工作年限'
    education = '教育水平'
    positionAdvantage = '职位诱惑'
    companyLabelList = '公司标签'
    userId = '用户ID'
    companyLogo = '公司logo'
    haveDeliver = ''
    score = ''
    adWord = ''
    adTimes = ''
    adBeforeDetailPV = ''
    adAfterDetailPV = ''
    adBeforeReceivedCount = ''
    adAfterReceivedCount = ''
    isCalcScore = ''
    searchScore = ''
    district = '城区'
    positionUrl = '岗位链接'
    companyUrl = '公司链接'

class Lagou(object):
    # 构建通用请求头
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Referer': '',  # url without '.json'
        #如果被反爬，cookie可能需要更新
        'Cookie': 'JSESSIONID=ABAAABAAAFCAAEGBBB4142F20938248BB2478F3E58144AC; Hm_lvt_4233e74dff0ae5bd0a3d81c6ccf756e6=1533828435; _ga=GA1.2.270700076.1533828435; user_trace_token=20180809232715-b1c8888a-9be8-11e8-b9f2-525400f775ce; LGUID=20180809232715-b1c88c33-9be8-11e8-b9f2-525400f775ce; X_HTTP_TOKEN=3086fbe35a0d1fd40e7578a16f535b8b; showExpriedIndex=1; showExpriedCompanyHome=1; showExpriedMyPublish=1; hasDeliver=0; index_location_city=%E5%B9%BF%E5%B7%9E; _gid=GA1.2.105723379.1533990288; TG-TRACK-CODE=hpage_code; _gat=1; LGSID=20180814012036-310b3c09-9f1d-11e8-a37b-5254005c3644; PRE_UTM=; PRE_HOST=; PRE_SITE=https%3A%2F%2Fwww.lagou.com%2Fgongsi%2FallCity.html%3Foption%3D163-0-0; PRE_LAND=https%3A%2F%2Fwww.lagou.com%2F; login=false; unick=""; _putrc=""; Hm_lpvt_4233e74dff0ae5bd0a3d81c6ccf756e6=1534180860; LGRID=20180814012059-3f3e3384-9f1d-11e8-a37b-5254005c3644',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
        'Connection': 'keep-alive',
        'Content-Length': '',
        'Host': 'www.lagou.com',
        'Origin': 'https://www.lagou.com'
    }

    # 连接数据库，数据库全部为protected
    _myclient = pymongo.MongoClient('localhost', 27017)
    _mydb = _myclient['lagoudb_backup']
    _url_col = _mydb['status_url']  #被成功请求过的url集合
    _company_col = _mydb['company_list']#所有公司的集合
    _city_col = _mydb['cities']#所有城市的集合
    _posit_list = _mydb['position_list']#公司列表的岗位集合
    _retry_times = 5       #用于重试的次数
    #按城市进行抓取
    def __init__(self,city='厦门'):
        self.city = city        #未校验城市名，默认为厦门


    def request_url(self,method,url,headers,**args):
        try:
            response = method(url,headers=headers,**args)
            # = response.content.decode('utf-8','ignore')  # html
            return response   # 返回响应
        except requests.exceptions.ConnectionError as e:
            print(e)
            Lagou._url_col.insert({'bad_url':url})  #记录错误的链接
            # self.request_url(method,url,headers) #retry暂未解决

    #判断url是否重复
    def is_repeat_url(self,url):
        if Lagou._url_col.find({'success_url': url}).count() != 0:
            return True

    #获取并存储拉勾上所有的城市列表
    def download_city(self):
        url = 'https://www.lagou.com/gongsi/allCity.html?option=215-0-0'
        #去重判断
        if self.is_repeat_url(url):
            print('已获取所有城市列表')
            return None
        #请求城市列表
        city_headers = Lagou.headers
        city_res = self.request_url(requests.get,url,city_headers)
        city_html = etree.HTML(city_res.content.decode('utf8','ignore'))
        city_lists = city_html.xpath('//table[@class="word_list"]/tr/td/ul/li/a')
        Lagou._url_col.insert({'success_url': url}) #添加已抓取的链接
        #数据入库
        for city in city_lists:
            Lagou._city_col.insert({'city_name':city.xpath('string(.)'),'city_url':city.xpath('string(./@href)')})
        print('all cities saved!')
        return None

    #获取指定城市的所有公司，返回状态码
    def get_company_list(self):
        #查找城市url
        city_col = Lagou._mydb.cities
        city_url = city_col.find_one({'city_name':self.city})['city_url']
        status_code = 1 #状态码用于表示抓取状态，默认1代表本次成功抓取该城市
        #去重判断
        if self.is_repeat_url(city_url+'.json'):
            print('%s 公司已抓取过'%self.city)
            status_code = 2  #状态码为2，表示该城市已经抓取
            return status_code
        #请求城市的公司列表
        cl_headers = Lagou.headers
        cl_headers['Referer'] = city_url
        cl_headers['User-Agent'] = Lagou.ua.random
        pn = 1
        while True:
            pyload = {
                'pn': pn,  # 第0页和第1页是一样的
                'first': False,
                'havemark': 0,
                'sortField': 0
            }
            company = {}
            company['uid'] = city_url + '.json?pageNo=%s' % str(pn)  # 添加一个id用于去重
            # 判断城市翻页是否重复
            if Lagou._company_col.find({'uid': company['uid']}).count() != 0:
                print('此页面已抓取')
                pn += 1
                continue

            company_res = self.request_url(requests.post,city_url+'.json',cl_headers,data=pyload)
            try:
                company_data = json.loads(company_res.text)
            except (TypeError,ValueError) as err:   #爬虫被识别可能无法返回json内容，需要retry
                print('Error:',err)
                print('爬虫被识别，稍等片刻...')
                sleep(random.uniform(0,30))       #随机休息30秒内的时间
                print('第%d次重试'%(Lagou._retry_times-self._retry_times+1))
                self._retry_times -= 1
                if self._retry_times <= 0:
                    print('%s无法成功抓取'%self.city)
                    status_code = 0#状态码为0，表示抓取有误
                    self._retry_times = Lagou._retry_times  # 重置实例的retry次数
                    return status_code
                return self.get_company_list()
            company = {**company,**company_data}

            try:
                if not company['result']: #终止条件
                    break
            except KeyError as e:   #判断是否被识别为爬虫
                print(e)
                continue
            Lagou._company_col.insert(company)#指定城市的公司存入数据库
            print('完成%s第%d页公司列表获取'%(self.city,pn))
            pn += 1
            sleep(random.random())  # 防止访问过快
        Lagou._url_col.insert({'success_url': city_url+'.json'}) #记录完成抓取的城市
        Lagou._city_col.update({'city_name':self.city},{'$set':{'city_status':1}})#讲抓取过的城市标记状态为1
        print('完成 %s 抓取'%self.city)
        status_code = 1
        return status_code#状态码默认值


    #执行获取所有城市的所有公司
    def all_city_company(self):
        self.download_city()    #抓取所有城市的链接，若已抓取，则跳过
        ccol = Lagou._city_col.find()
        count = 1
        for city in ccol:
            start_time = time()
            self.city = city['city_name']
            # self.city = '深圳'
            print('开始抓取%s的公司'%self.city)
            if self.get_company_list() == 1:  #状态码为1，正常执行
                end_time = time()
                print('完成第%d个城市的抓取，还剩%d个城市;耗时%d秒' % (count, ccol.count() - count, end_time - start_time))
                print('------------------------------------------')
                sleep(random.uniform(0, 30))  # 每抓完一个城市休息0~30秒
                count += 1
                # continue  #若以下语句有本次循环的其他语句则continue
            elif self.get_company_list() == 2:  #判断已经抓取则进入下一个城市
                print('已完成第%d个城市的抓取，还剩%d个城市' % (count, ccol.count() - count))
                print('------------------------------------------')
                count += 1
                # continue  #若以下语句有本次循环的其他语句则continue
            else:
                print('%s有误，无法完成抓取，尝试下一个城市'%self.city)
                # continue  #若以下语句有本次循环的其他语句则continue
        print('完成所有城市的获取！！')



    # 从数据库获取所有公司的id和公司名
    def get_all_company_id(self):
        com_data = self._company_col.find()
        id_set = set()
        company_list = []
        for city in com_data:
            for company_result in city['result']:
                company_list.append({'companyId':company_result['companyId'],'companyName':company_result['companyShortName']})
        #公司去重，将list中的dict转化为set，可被hash，然后通过set去重，再添加进新的list
        uni_company_list = []
        for company in company_list:
            t = tuple(company.items())
            if t not in id_set:
                id_set.add(t)
                uni_company_list.append(company)
        return uni_company_list

    #获取某公司的所有岗位列表并存入数据库,返回岗位数量
    def get_position_list(self,company_id,company_name):
        pn = 1
        position_list = []
        position_num = 0
        #公司去重
        if self._posit_list.find({'companyId':company_id}).count() != 0:
            print('%s 已抓取过'%company_name)
            return None

        position_url = 'https://www.lagou.com/gongsi/searchPosition.json'
        position_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'https://www.lagou.com/gongsi/j%d.html'%company_id,
            'User-Agent':Lagou.ua.random,
            'cookie': "_ga=GA1.2.114206061.1534349928; user_trace_token=20180816001847-e38dd0ee-a0a6-11e8-a80e-5254005c3644; LGUID=20180816001847-e38dd425-a0a6-11e8-a80e-5254005c3644; index_location_city=%E5%85%A8%E5%9B%BD; JSESSIONID=ABAAABAAAFCAAEG6FF3CE1C8E47BAB7CCCDB33075D30323; _gid=GA1.2.1677924342.1534584164; Hm_lvt_4233e74dff0ae5bd0a3d81c6ccf756e6=1534349928,1534584164; SEARCH_ID=fceafb3b625d49168771da7d9d5550d1; TG-TRACK-CODE=hpage_code; LGRID=20180818191151-81f97c1b-a2d7-11e8-923c-525400f775ce; Hm_lpvt_4233e74dff0ae5bd0a3d81c6ccf756e6=1534590712",
            'connection': "keep-alive"
        }
        while True:
            pyload = {
                 'companyId':company_id,
                 'positionFirstType':'全部',
                 'pageNo':pn
            }
            position_res = self.request_url(requests.post, position_url, headers=position_headers, data=pyload)
            try:#处理反爬返回结果非json的情况
                position_data = json.loads(position_res.text)
            except Exception as e:#异常类型写错则无法捕获
                print('anti-spider[no json]:',e)
                print('爬虫被识别，第{}次重试'.format(Lagou._retry_times-self._retry_times+1))
                self._retry_times -= 1
                if self._retry_times <= 0:
                    print('%s 公司抓取失败'%company_name)
                    self._retry_times = Lagou._retry_times
                    return None
                sleep(random.uniform(0,10))
                return self.get_position_list(company_id,company_name)#重试

            try:  # 反爬返回结果为json，但无result的json的情况
                if not position_data['content']['data']['page']['result']:  # 终止条件
                    print('{0} 公司岗位抓取完毕'.format(company_name))
                    break
            except (KeyError,TypeError) as e:
                print('anti-spider[wrong json format]:', e)
                continue
            position_list.append(position_data)
            position_num += len(position_data['content']['data']['page']['result'])  # 累计岗位数量
            print('{0} 第 {1} 页岗位抓取完毕'.format(company_name, pn))
            # self._posit_list.insert(dict({'companyId': company_id}, **position_data))
            pn += 1
            # sleep(random.uniform(0,1))

        self._posit_list.insert(dict({'companyId':company_id,'companyUrl':'https://www.lagou.com/gongsi/j%d.html'%company_id},**{'allContent':position_list})) #所有岗位列表都取到才存入数据库
        print('%s 完成 %d 个岗位获取，并存入数据库'%(company_name,position_num))

    #更新数据使用update 示例
    # col = mydb['company_list']
    # url = 'https://www.lagou.com/gongsi/215-0-0.json?pageNo='
    # for i in col.find():
    #     col.update({'_id': i['_id']}, {'$set': {'uid': url + str(i['pageNo'])}})

    #获取岗位的详情并存入数据库
    def posititon_detail(self,position):
        pass

    #获取所有公司岗位列表
    def all_posit_list(self):
        company_list = self.get_all_company_id()
        already_company_id = []
        for already_company in list(self._posit_list.find()):
            already_company_id.append(already_company['companyId'])
        company_num = len(company_list)
        count = 1
        for company in company_list:
            company_id = company['companyId']
            company_name = company['companyName']
            if company_id in already_company_id:#重启时，检测最后的状态
                print('%s已经获取'%company_name)
                count += 1
                continue
            print('开始获取%s 岗位信息...'%company_name)
            start_time = time()
            self.get_position_list(company_id,company_name)
            # print(company_id,company_name)
            end_time = time()
            print('总共{0}个公司，完成第{1}个，剩余{2}个，耗时{3:.2f}秒'.format(company_num,count,company_num-count,end_time-start_time))
            print('------------------------------')
            count += 1
            sleep(random.uniform(0,0.5))
        print('完成所有公司的岗位获取！')


    def del_repeat_data(self):
        company_list = Lagou._posit_list.find()
        com_id_set = set()
        for company in company_list:
          if company['companyId'] not in com_id_set:
              com_id_set.add(company['companyId'])
          else:
              col.delete_one(company)
        posit_sum = 0
        for company in Lagou._posit_list.find():
	         for content in company['allContent']:
		          posit_sum += len(content['content']['data']['page']['result'])
        print('完成数据去重，最终保留 %d 个公司，%d 个岗位'%(len(com_id_set),posit_sum))

    #将制定格式保存为csv
    def data_to_csv(self):
        posit_cursor = self._posit_list.find()
        posit_count = 0
        company_count = 0
        position_list = []
        posit_field = [Field.positionName, Field.companyName, Field.companyFullName, Field.positionUrl,
                       Field.companyUrl, Field.jobNature, Field.financeStage, Field.companySize, Field.industryField,
                       Field.city, Field.district, Field.createTime, Field.salary, Field.workYear, Field.education,
                       Field.positionAdvantage, Field.companyLabelList, Field.companyLogo]

        start_time = time()
        for results in posit_cursor:
            for data in results['allContent']:
                positions = data['content']['data']['page']['result']
                for posit in positions:
                    posit_data = {}
                    for field in posit_field:
                        if field.name == 'positionUrl':
                            posit_data[field.value] = 'https://www.lagou.com/jobs/%d.html' % posit[
                                Field.positionId.name]
                            continue
                        if field.name == 'companyUrl':
                            posit_data[field.value] = 'https://www.lagou.com/gongsi/%d.html' % posit[
                                Field.companyId.name]
                            continue
                        if field.name == 'district':
                            if 'district' not in posit.keys():
                                posit_data[field.value] = ''
                                continue
                        posit_data[field.value] = posit[field.name]
                    # print(posit_data)
                    posit_count += 1
                    position_list.append(posit_data)
            company_count += 1
        df = pd.DataFrame(position_list, columns=[field.value for field in posit_field])
        df.to_csv('lagou_data.csv', encoding='utf-8')
        end_time = time()
        print('共输出 %d 个公司，%d 个岗位，共耗时%.2f秒' % (company_count, posit_count, (end_time - start_time)))


    # 打包拉勾爬虫：所有城市-所有企业-所有岗位
    def main(self):
        self.all_posit_list()
        self.del_repeat_data()
        self.data_to_csv()

if __name__ == '__main__':
    lg = Lagou()
    lg.main()









