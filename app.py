from flask import Flask, render_template, request
import re
import os
import time
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from pymongo import MongoClient
import threading
import datetime

load_dotenv()

grade_to_points = {
    'A+': 10,
    'A': 9,
    'B': 8,
    'C': 7,
    'D': 6,
    'E': 5,
    'F': 0
}

credits_r20_cse = {
    'I': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Lab1": 1.5,
        "Lab2": 1.5,
        "Lab3": 3,
        "Lab4": 1.5,
        "Lab5": 0
    },
    'II': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 2,
        "Lab1": 1.5,
        "Lab2": 1,
        "Lab3": 1.5,
        "Lab4": 1.5,
        "Lab5": 0
    },
    'III': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 3,
        "Lab1": 1.5,
        "Lab2": 1.5,
        "Lab3": 1.5,
        "Lab4": 2,
        "Lab5": 0
    },
    'IV': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 3,
        "Lab1": 1.5,
        "Lab2": 1.5,
        "Lab3": 1.5,
        "Lab4": 2,
        "Lab5": 0
    },
    'V': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 3,
        "Lab1": 1.5,
        "Lab2": 1.5,
        "Lab3": 1.5,
        "Lab4": 2
    },
    'VI': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 3,
        "Lab1": 1.5,
        "Lab2": 1.5,
        "Lab3": 1.5,
        "Lab4": 2
    },
    'VII': {
        "Sub1": 3,
        "Sub2": 3,
        "Sub3": 3,
        "Sub4": 3,
        "Sub5": 3,
        "Sub6": 3,
        "Lab1": 3,
        "Lab2": 2
    },
    'VIII': {
        "Lab1": 12
    }
}

def ping_server():
    URL = "https://rvr-results.onrender.com/ping/"
    while True:
        x = datetime.datetime.now()
        try:
            requests.get(URL)
            print("Server pinged successfully at: ", x)
        except requests.RequestException as e:
            print(f"Error pinging server: {e} at: ", x)
        time.sleep(10 * 60) # 10 min

def calculate_results(reg_no):
    tot_gpa = {}
    cumulative_gpa = {}
    results = {}
    name = ""
    no_of_requests = 0
    while no_of_requests < 3:
        no_of_requests += 1
        
        try:
            url = "https://rvrjcce.ac.in/examcell/results/regnoresultsR1.php?q=" + reg_no
            response = requests.get(url)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                div_content = soup.find('div', class_='wrapper col4')
                
                if div_content:
                    print("content retrived")
                    first_table = div_content.find('table')
                    first_row = first_table.find('tr') 
                    tds = first_row.find_all('td')
                    name = re.search(r'Name : (.+)', tds[0].text).group(1)
                    matches = []
                    if first_table:
                        rows = first_table.find_all('tr')
                        for row in rows[2:]:
                            cols = row.find_all('td')
                            if len(cols) >= 2:
                                semester_number = cols[0].text.strip().split()[1]
                                grades = ' '.join(col.text.strip() for col in cols[1:])
                                matches.append((semester_number, grades))
                    print("=========\n", matches, "\n===========")
                    subjects = ["Sub1", "Sub2", "Sub3", "Sub4", "Sub5", "Sub6", "Sub7"]
                    labs = ["Lab1", "Lab2", "Lab3", "Lab4", "Lab5", "Lab6"]
                    
                    grades = defaultdict(dict)
                    
                    for match in matches:
                        semester = match[0]
                        grades_list = match[1].split()
                        for i, grade in enumerate(grades_list):
                            if i < len(subjects):
                                subject = subjects[i]
                            else:
                                subject = labs[i - len(subjects)]
                            grades[semester][subject] = grade

                    grades = dict(grades)
                    for semester, subjects in grades.items():
                        results[semester] = {}
                        for subject, grade in subjects.items():
                            if grade != "--":
                                results[semester][subject] = grade
                    
                    sum_of_tot_cred = 0
                    for sem in results.keys():
                        sem_gpa = 0
                        for sub in results[sem].keys():
                            sem_gpa += credits_r20_cse[sem][sub]*grade_to_points[results[sem][sub]]
                        sem_gpa = sem_gpa/sum(credits_r20_cse[sem].values())
                        tot_gpa[sem] = sem_gpa
                        cur_cred = sum(credits_r20_cse[sem].values())
                        sum_of_tot_cred += cur_cred
                        sum_of_gpa_cred = 0
                        for sem, gpa in tot_gpa.items():
                            sum_of_gpa_cred += sum(credits_r20_cse[sem].values())*gpa
                        cumulative_gpa[sem] = round(sum_of_gpa_cred/sum_of_tot_cred, 2)
                else:
                    print( "No content found in div with id 'txtHint'")
            else:
                print( "Error: Unable to fetch data")
        except Exception as error:
            print("Failed to reach server", error)
            
        if cumulative_gpa:
            break
        
        time.sleep(5)
        
    else:
        return "server down", {}, {}, {}
    for key in tot_gpa:
        tot_gpa[key] = round(tot_gpa[key], 2)
    return name, results, tot_gpa, cumulative_gpa

def store_results(name, reg_no, results, tot_gpa, cumulative_gpa):
    user = os.getenv('USER')
    password = os.getenv('PASSWORD')
    database = os.getenv('DB')
    collection = os.getenv('COLLECTION')
    url = "mongodb+srv://"+user+":"+password+"@studentresults.o3jkbq0.mongodb.net/?retryWrites=true&w=majority&appName=StudentResults"
    
    client = MongoClient(url)
    db = client[database]
    collection = db[collection]
    filter = {"reg_no": reg_no}
    document_data = {
        "$set": {
            "reg_no": reg_no,
            "name": name,
            "results": results,
            "tot_gpa": tot_gpa,
            "cumulative_gpa": cumulative_gpa
        }
    }
    collection.update_one(filter, document_data, upsert=True)
    client.close()
    
def reteive_previous_search_results(reg_no):
    user = os.getenv('USER')
    password = os.getenv('PASSWORD')
    database = os.getenv('DB')
    collection = os.getenv('COLLECTION')
    url = "mongodb+srv://"+user+":"+password+"@studentresults.o3jkbq0.mongodb.net/?retryWrites=true&w=majority&appName=StudentResults"
    
    client = MongoClient(url)
    db = client[database]
    collection = db[collection]
    prev_result = collection.find_one({"reg_no": reg_no})
    return prev_result
    
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping')
def ping():
    return f'pinging server', 200

@app.route('/result', methods=['POST'])
def result():
    reg_no = request.form['input_text']
    reg_no = reg_no.lower()
    name, results, tot_gpa, cumulative_gpa = calculate_results(reg_no)
    result_type = None
    if name == "Invalid reg no":
        return f"Invalid reg no", 404
    elif name and results and tot_gpa and cumulative_gpa:
        print("new result")
        result_type = "new result"
        store_results(name, reg_no, results, tot_gpa, cumulative_gpa)
    else:
        prev_result = reteive_previous_search_results(reg_no)
        if not prev_result:
            return f"Server down, No saved results found", 404
        else:
            print("old result")
            name = prev_result.get("name")
            reg_no = prev_result.get("reg_no")
            results = prev_result.get("results")
            tot_gpa = prev_result.get("tot_gpa")
            cumulative_gpa = prev_result.get("cumulative_gpa")
    return render_template('result.html', name=name, reg_no=reg_no, results=results, tot_gpa=tot_gpa, cumulative_gpa=cumulative_gpa, results_type=result_type)


if __name__ == '__main__':
    ping_thread = threading.Thread(target=ping_server)
    ping_thread.daemon = True
    ping_thread.start()
    app.run(host='0.0.0.0', port=5000)
