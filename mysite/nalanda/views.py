from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.template import Context, loader
from django.core.exceptions import ObjectDoesNotExist
from nalanda.models import Users,UserInfoSchool, UserInfoClass, UserRoleCollectionMapping, UserInfoStudent
from nalanda.models import Content, MasteryLevelStudent, MasteryLevelClass, MasteryLevelSchool, LatestFetchDate
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.contrib.auth import logout
from django.utils import timezone
from django.db.utils import DatabaseError, Error, OperationalError
from django.core.urlresolvers import reverse
from django.core import serializers
from django.db import models
import json
import datetime
import time


def construct_response(code, title, message, data):
    response_object = {}
    response_object['code'] = code
    response_object['info'] = {'title': title,'message': message}
    response_object['data'] = data
    return response_object            


def login_post(username, password):
    try:
        is_success = False
        code = 0
        role = -1
        title = ""
        message = ""
        data = {}
        if username and password:     
            result = Users.objects.filter(username=username).filter(password=password)
            if not result:
                code = 1001
                title = 'The username/password combination used was not found on the system'
                message = 'The username/password combination is incorrect'
                data = {'username': username} 
                user = Users.objects.filter(username=username)
                if user and user.role_id != 4:
                    user[0].number_of_failed_attempts += 1
                    if user[0].number_of_failed_attempts >= 4:
                        user[0].is_active = False
                    user[0].save()
            else:
                if result[0].number_of_failed_attempts >= 4:
                    print("failed attempts:", result[0].number_of_failed_attempts)
                    code = 1002
                    title = 'Sorry, you have been blocked'
                    message = 'The user has been blocked'
                    data = {'username': username} 
                else:
                    result[0].last_login_time = timezone.now()
                    result[0].save()
                    role = result[0].role_id
                    is_success = True
            
        else:
            code = 1003
            title = 'The username/password are required'
            message = 'The username/password are required'
            data = {'username': username}
            is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success, role
    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success, role
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success, role
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success, role
    

@csrf_exempt
def login_view(request):
    if request.method == 'GET':
        return render(request, 'login.html')
        
    elif request.method == 'POST':
        data = json.loads(request.body)

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        response_object, is_success, role = login_post(username, password)
        

        if is_success:
            response = redirect(reverse('report'))
            response.set_cookie('role', role)
        else:    
            response = render(request, 'login.html', response_object) 
            response.delete_cookie('role')
        response.delete_cookie('username')
        return response


@csrf_exempt
def logout_view(request):
    if request.method == 'GET':
        try:
            logout(request)
            code = 0
            title = ""
            message = ""
            data = {}
            response_object = construct_response(code, title, message, data)
            response = render(request, 'index.html', response_object)
            response.delete_cookie('role')
            return response
        except:
            code = 2021
            title = 'Sorry, error occurred at the server'
            message = 'Sorry, error occurred at the server'
            data = {} 
            response_object = construct_response(code, title, message, data)
            return HttpResponse(response_object)


def get_school_and_classes():
    institutes = []
    school_info = {}
    school_id = ''
    school_name = ''
    school = UserInfoSchool.objects.all()
    if school:
        for i in range(0, len(school)):
            school_id = school[i].school_id
            school_name = school[i].school_name
            classes_array = []
            classes_in_school = UserInfoClass.objects.filter(parent=school_id)
            if classes_in_school:
                for i in range(0, len(classes_in_school)):
                    current_class = {'name': classes_in_school[i].class_name, 'id': classes_in_school[i].class_id}
                    classes_array.append(current_class)
            school_info = {'name': school_name, 'id': school_id, 'classes': classes_array}
            institutes.append(school_info)
    return institutes
 

        

@csrf_exempt
def register_post(username, password, first_name, last_name, email, role_id, institute_id, classes): 
    try:
        not_complete = False
        username_exists = False
        is_success = False
        if (not username) or (not password) or (not email) or (not role_id) or role_id == '0' or (not first_name) or (not last_name):
            not_complete = True
        
        if (role_id == '2' or role_id == '3') and (not institute_id):
            not_complete = True
        
        if role_id == '3' and (not classes):
            not_complete = True

        if not not_complete:
            user = Users.objects.filter(username=username)
            if user:
                username_exists = True

        if not_complete:
            code = 1004
            title = 'The registration info provided is not complete'
            message = 'The registration info provided is not complete'           

        elif username_exists:
            code = 1005
            title = 'The username already exists'
            message = 'The username already exists'
        
        role_id = int(role_id)  
        if not institute_id:
            institute_id = ''
        else:
            institute_id = int(institute_id)

        if not_complete or username_exists:
            autoComplete = {'username': username, 'firstName': first_name, 'lastName': last_name, 'email': email, 'role': role_id, 'instituteId': institute_id, 'classes': classes}
            institutes = get_school_and_classes()
            data = {'autoComplete': autoComplete, 'institutes': institutes}   
            is_success = False

        else:
            number_of_failed_attempts = 0
            create_date = timezone.now()
            new_user = Users(username=username, password=password, first_name=first_name, last_name=last_name, email=email, number_of_failed_attempts=number_of_failed_attempts, create_date=create_date, role_id=role_id)
            new_user.save()
            if role_id == '1':
                user_role_collection_mapping = UserRoleCollectionMapping(user_id=new_user)
                user_role_collection_mapping.save()
            elif role_id == '2':
                school = UserInfoSchool.objects.filter(school_id=int(institute_id))
                if school:
                    user_role_collection_mapping = UserRoleCollectionMapping(user_id=new_user, institute_id=school[0])
                    user_role_collection_mapping.save()
            elif role_id == '3':
                school = UserInfoSchool.objects.filter(school_id=int(institute_id))
                if school:
                    for i in range(0, len(classes)):
                        current_class = UserInfoClass.objects.filter(class_id=classes[i])
                        if current_class:
                            user_role_collection_mapping = UserRoleCollectionMapping(user_id=new_user, institute_id=school[0], class_id = current_class[0])
                            user_role_collection_mapping.save()         
            code = 0
            title = ''
            message = ''
            data = {}
            is_success = True
        response_object = construct_response(code, title, message, data)
        return response_object, is_success

    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success


@csrf_exempt
def register_view(request):
    if request.method == 'GET':
        institutes = get_school_and_classes()
        data = {'institutes': institutes}   
        code = 0
        title = ''
        message = ''
        response_object = construct_response(code, title, message, data)
        return render(request, 'register.html', response_object)  

    elif request.method == 'POST':
        data = json.loads(request.body)

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        email = data.get('email', '').strip()
        role_id = str(data.get('role', '')).strip()
        institute_id = str(data.get('instituteId', '')).strip()
        classes = data.get('classes', [])
        
        response_object, is_success = register_post(username, password, first_name, last_name, email, role_id, institute_id, classes)
        print(response_object)
        
        if is_success:
            response = redirect(reverse('login'))
        else:
            response = render(request, 'register.html', response_object) 
        return response

    

 

def admin_approve_pending_users_post(users):
    try:
        code = 0
        title = ''
        message = ''
        data = {}

        if len(users) != 0:
            for i in range(len(users)):
                username = users[i]["username"]
                result = Users.objects.filter(username=username)
                if result:
                    result[0].is_active = True
                    result[0].update_date = timezone.now()
                    result[0].save()
                    # If the user is a board memeber, no institute or class will be specified 
                    if result[0].role_id == 1 or result[0].role_id == 2:
                        mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0])
                        if mapping:
                            mapping[0].is_approved = True
                            mapping[0].approver_id = 1
                            mapping[0].save()
                    elif result[0].role_id == 3:
                        classes = users[i]["classes"]
                        for j in range(len(classes)):
                            approve_class = UserInfoClass.objects.filter(class_id = classes[j])
                            if approve_class:
                                mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0]).filter(class_id=approve_class[0])
                                if mapping:
                                    mapping[0].is_approved = True
                                    mapping[0].approver_id = 1
                                    mapping[0].save()
        response_object = construct_response(code, title, message, data) 
       
        return response_object

    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object



   
@csrf_exempt
def admin_approve_pending_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        if role != '5':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)

        else:
            data = json.loads(request.body)
            users = data.get('users',[])       
            response_object = admin_approve_pending_users_post(users)
        return HttpResponse(response_object)


def admin_disapprove_pending_users_post(users): 
    code = 0
    title = ''
    message = ''
    data = {}
    try:
        if users:
            for i in range(len(users)):
                username = users[i]['username']
                result = Users.objects.filter(username=username)
                if result:
                    result[0].update_date = timezone.now()
                    result[0].save()
                    # If the user is a board memeber, no institute or class will be specified 
                    if result[0].role_id == 1 or result[0].role_id == 2:
                        mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0])
                        if mapping:
                            mapping[0].delete()
                            
                    elif result[0].role_id == 3:
                        classes = users[i]["classes"]
                        for j in range(len(classes)):
                            approve_class = UserInfoClass.objects.filter(class_id = classes[j])
                            if approve_class:
                                mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0]).filter(class_id=approve_class[0])
                                if mapping:
                                    mapping[0].delete()               
        response_object = construct_response(code, title, message, data) 
        return response_object
    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object

@csrf_exempt
def admin_disapprove_pending_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        if role != '5':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)

        else:
            data = json.loads(request.body)
            users = data.get('users',[])       
            response_object = admin_disapprove_pending_users_post(users)
        return HttpResponse(response_object)
    

def admin_unblock_users_post(usernames):
    code = 0
    title = ''
    message = ''
    data = {}
    try:
        if usernames:
            for i in range(len(usernames)):
                username = usernames[i]
                result = Users.objects.filter(username=username)
                if result:
                    result[0].is_active = True;
                    result[0].number_of_failed_attempts = 0;
                    result[0].update_date = timezone.now()
            
                    result[0].save()
        response_object = construct_response(code, title, message, data) 
        return response_object
    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object



    
@csrf_exempt
def admin_unblock_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        if role != '5':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)

        else:
            data = json.loads(request.body)
            usernames = data.get('usernames',[])
            response_object = admin_unblock_users_post(usernames)

        return HttpResponse(response_object)

@csrf_exempt
def report_homepage_view(request):
    if request.method == 'GET':
        role = request.COOKIES.get('role')
        if not role:
            code = 2031
            title = 'Sorry, you have to login to perform this action'
            message = 'Sorry, you have to login to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            return HttpResponse(response_object)

        else:
            code = 0
            title = ''
            message = ''
            try:
                lastest_date = LatestFetchDate.objects.filter()
                if lastest_date:
                    data = {'dateUpdated': lastest_date[0].lastest_date}
                else:
                    data = {}
                response_object = construct_response(code, title, message, data)
                return render(request, 'report-mastery.html', response_object)
            except DatabaseError:
                code = 2001
                title = 'Sorry, error occurred in database operations'
                message = 'Sorry, error occurred in database operations'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'report-mastery.html', response_object)
            except OperationalError:
                code = 2011
                title = 'Sorry, operational error occurred'
                message = 'Sorry, operational error occurred'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'report-mastery.html', response_object)
            except:
                code = 2021
                title = 'Sorry, error occurred at the server'
                message = 'Sorry, error occurred at the server'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'report-mastery.html', response_object)

     
            


def construct_breadcrumb(parentName, parentLevel, parentId):
    res = {
        "parentName": parentName,
        "parentLevel": parentLevel,
        "parentId": parentId
        }

    return res

def construct_metrics():
    metrics = [
        {},
        {'displayName': '% exerciese completed', 'toolTip': ''},
        {'displayName': '% exerciese correct', 'toolTip': ''},
        {'displayName': '# attempts completed', 'toolTip': ''},
        {'displayName': '% students completed the topic', 'toolTip': ''},
        {}
    ]
    return metrics


def get_page_meta(parent_id, parent_level):
    try:
        code = 0
        title = ''
        message = ''
        if parent_level == -1 or parent_id == -1:
            code = 2031
            title = 'Parent level or parent id is missing'
            message = 'Parent level or parent id is missing'
            data = {} 
        else: 
            metrics = construct_metrics()
            breadcrumb = []
            rows = []
            root = construct_breadcrumb("Institutues", 0, 0)
            # For all possbile levels, root should be present
            breadcrumb.append(root)
            #If the partent level is root
            if parent_level == 0:
                # Return all the schools 
                schools = UserInfoSchool.objects.filter()
                if schools:
                    for school in schools:
                        temp = {
                            "id": school.school_id,
                            "name": school.school_name
                        }
                        rows.append(temp)
            # If the parent level is school
            elif parent_level == 1:
                # Add current level school to the breadcrumb
                school = UserInfoSchool.objects.filter(school_id = parent_id)
                if school:
                    school_name = school[0].school_name
                    breadcrumb.append(construct_breadcrumb(school_name, 1, parent_id))

                # Return all the classrooms inside a school

                    classes = UserInfoClass.objects.filter(parent = school[0])
                    if classes:
                        for curr_class in classes:
                            temp = {
                                "id": curr_class.class_id,
                                "name": curr_class.class_name
                            }
                            rows.append(temp)

            elif parent_level == 2:
                
                #Add current level class to the breadcrumb
                curr_class = UserInfoClass.objects.filter(class_id = parent_id)
                if curr_class:
                    class_name = curr_class[0].class_name
                   
                #Add higher level school to the breadcrumb
                    school = curr_class[0].parent
                    if school:
                        school_id = school.school_id
                        school_name = school.school_name
                        breadcrumb.append(construct_breadcrumb(school_name, 2, school_id))
                        breadcrumb.append(construct_breadcrumb(class_name, 2, parent_id))

                    # Return all students inside a classroom
                students = UserInfoStudent.objects.filter(parent = curr_class[0])
                if students:
                    for student in students:
                        temp = {
                            'id': student.student_id,
                            'name': student.student_name
                        }
                        rows.append(temp)
            data = {'breadcrumb': breadcrumb, 'metrics': metrics, 'rows': rows}
        response_object = construct_response(code, title, message, data)
        return response_object
    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object


@csrf_exempt
def get_page_meta_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        if not role:
            code = 2031
            title = 'Sorry, you have to login to perform this action'
            message = 'Sorry, you have to login to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)

            return HttpResponse(response_object)

        else:
            data = json.loads(request.body)
            start_timestamp = data.get('startTimestamp', '').strip()
            end_timeStamp = data.get('endTimeStamp', '').strip()
            topic_id = data.get('topicId', -2)
            parent_level = data.get('parentLevel', -1)
            parent_id = data.get('parentId', -1)
            response_object= get_page_meta(parent_id, parent_level) 
          
            return HttpResponse(response_object)
        
        
def get_page_data(parent_id, parent_level, topic_id, end_timeStamp, start_timestamp):
    try:
        start_timestamp = datetime.date(2015,1,1)
        end_timeStamp = datetime.date(2015,5,5)
        code = 0
        title = ''
        message = ''
        if parent_level == -1 or parent_id == -1 or topic_id == -2 or (not start_timestamp) or (not end_timeStamp) or channel_id == -1:
            code = 2031
            title = 'Argument is missing'
            message = 'Argument is missing'
            data = {} 
        else: 
            rows = []
            aggregation = []
            percent_complete_array = []
            percent_correct_array = []
            number_of_attempts_array = []
            percent_student_completed_array = []

            values = []
            total_questions = 0
            
            # If the user wants to view everything
            if topic_id == -1:
                topics = Content.objects.filter()
                if topics:
                    for topic in topics:
                        total_questions += topic.total_questions

            else:
                topic = Content.objects.filter(content_id=topic_id).filter(channel_id = channel_id)
                if topic:
                    total_questions = topic[0].total_questions

            # If the current level is root
            if parent_level == 0:
                # Return all the schools 
                schools = UserInfoSchool.objects.filter()
                # For each school, calculate
                if schools:
                    for school in schools:
                        # Get school id and name
                        school_id = school.school_id
                        school_name = school.school_name
                        # Filter mastery level belongs to a certain school with certain topic id, and within certain time range
                        if topic_id == -1:
                            mastery_school = MasteryLevelSchool.objects.filter(school_id=school).filter(channel_id=channel_id).filter(date__range=(start_timestamp, end_timeStamp))
                        else:
                            mastery_school = MasteryLevelSchool.objects.filter(school_id=school).filter(channel_id=channel_id).filter(content_id=topic).filter(date__range=(start_timestamp, end_timeStamp))
                        if mastery_school:
                            # Calculate the percentage of completed questions
                            completed_questions = mastery_school[0].completed_questions
                            percent_complete_float = float(completed_questions) / total_questions
                            percent_complete = "{0:.2f}%".format(percent_complete_float)
                            percent_complete_array.append(percent_complete_float)

                            # Calculate the percentage of correct questions
                            correct_questinos = mastery_school[0].correct_questions
                            percent_correct_float = float(correct_questions) / total_questions
                            percent_correct = "{0:.2f}%".format(percent_correct_float)
                            percent_correct_array.append(percent_correct_float)

                            # Get the number of attempted questions
                            number_of_attempts = mastery_school[0].attempt_questions
                            number_of_attempts_array.append(number_of_attempts)

                            # Calculate the percentage of students completed the topic
                            total_students = school.total_students
                            students_completed = mastery_school[0].students_completed
                            percent_student_completed_float = float(students_completed) / total_students
                            percent_student_completed = "{0:.2f}%".format(percent_student_completed_float)
                            percent_student_completed_array.append(percent_student_completed_float)

                            values = [percent_complete, percent_correct, number_of_attempts, percent_student_completed]
                            row = {'id': school_id, 'name': school_name, 'values': values}
                            rows.add(row)

            # If the parent level is school
            elif parent_level == 1:
                # Find the current school
                school = UserInfoSchool.objects.filter(school_id = parent_id)
                # Return all the classrooms inside a school
                if school:
                    classes = UserInfoClass.objects.filter(parent = school[0])
                    if classes:
                        for curr_class in classes:
                            class_id = curr_class.class_id
                            class_name = curr_class.class_name
                            # Filter mastery level belongs to a certain class with certain topic id, and within certain time range
                            if topic_id == -1:
                                mastery_class = MasteryLevelClass.objects.filter(class_id=curr_class).filter(channel_id=channel_id).filter(date__range=(start_timestamp, end_timeStamp))
                            else:
                                mastery_class = MasteryLevelClass.objects.filter(class_id=curr_class).filter(content_id=topic).filter(channel_id=channel_id).filter(date__range=(start_timestamp, end_timeStamp))
                            if mastery_class:
                                # Calculate the percentage of completed questions
                                completed_questions = mastery_class[0].completed_questions
                                percent_complete_float = float(completed_questions) / total_questions
                                percent_complete = "{0:.2f}%".format(percent_complete_float)
                                percent_complete_array.append(percent_complete_float)


                                # Calculate the percentage of correct questions
                                correct_questinos = mastery_school[0].correct_questions
                                percent_correct_float = float(correct_questions) / total_questions
                                percent_correct = "{0:.2f}%".format(percent_correct_float)
                                percent_correct_array.append(percent_correct_float)

                                # Get the number of attempted questions
                                number_of_attempts = mastery_class[0].attempt_questions
                                number_of_attempts_array.append(number_of_attempts)

                                # Calculate the percentage of students completed the topic
                                total_students = school.total_students
                                students_completed = mastery_school[0].students_completed
                                percent_student_completed_float = float(students_completed) / total_students
                                percent_student_completed = "{0:.2f}%".format(percent_student_completed_float)
                                percent_student_completed_array.append(percent_student_completed_float)

                                values = [percent_complete, percent_correct, number_of_attempts, percent_student_completed]
                                row = {'id': school_id, 'name': school_name, 'values': values}
                                rows.add(row)

            # If the parent level is class
            elif parent_level == 2:

                curr_class = UserInfoClass.objects.filter(class_id = parent_id)
                # Return all the classrooms inside a school
                if curr_class:
                    students = UserInfoStudent.objects.filter(parent = curr_class[0])
                    if students:
                        for student in students:
                            student_id = student.student_id
                            student_name = student.student_name
                            # Filter mastery level belongs to a certain student with certain topic id, and within certain time range
                            if topic_id == -1:
                                mastery_class = MasteryLevelStudent.objects.filter(class_id=curr_class).filter(channel_id=channel_id).filter(date__range=(start_timestamp, end_timeStamp))
                            else:
                                mastery_student = MasteryLevelStudent.objects.filter(class_id=curr_class).filter(content_id=topic).filter(channel_id=channel_id).filter(date__range=(start_timestamp, end_timeStamp))
                            if mastery_student:
                                # Calculate the percentage of completed questions
                                percent_complete_float = float(completed_questions) / total_questions
                                percent_complete = "{0:.2f}%".format(percent_complete_float)
                                percent_complete_array.append(percent_complete_float)


                                # Calculate the percentage of correct questions
                                correct_questinos = mastery_school[0].correct_questions
                                percent_correct_float = float(correct_questions) / total_questions
                                percent_correct = "{0:.2f}%".format(percent_correct_float)
                                percent_correct_array.append(percent_correct_float)

                                # Get the number of attempted questions
                                number_of_attempts = mastery_student[0].attempt_questions
                                number_of_attempts_array.append(number_of_attempts)

                                # Return if this student has completed the topic
                                completed = mastery_student[0].completed
                                if completed:
                                    percent_student_completed = 1
                                else:
                                    percent_student_completed = 0
                                percent_student_completed_array.append(percent_student_completed)

                                values = [percent_complete, percent_correct, number_of_attempts, percent_student_completed]
                                row = {'id': school_id, 'name': school_name, 'values': values}
                                rows.add(row)
            avg_percent_complete = 0
            avg_percent_correct = 0
            avg_number_of_attempts = 0
            avg_percent_student_completed = 0

            for i in range(len(percent_complete_array)):
                avg_percent_complete +=  percent_complete_array[i]
                avg_percent_correct += percent_correct_array[i]
                avg_number_of_attempts += number_of_attempts_array[i]
                avg_percent_student_completed += percent_student_completed_array[i]
            avg_percent_complete /= 4
            avg_percent_correct /= 4
            avg_number_of_attempts /= 4
            if parent_level == 2:
                avg_percent_student_completed = ""
            else:
                 avg_percent_student_completed /= 4
            values = [str(avg_percent_complete), str(avg_percent_correct), str(avg_number_of_attempts), str(avg_percent_student_completed)]
            average = {'name': 'Average', 'values': values}
            aggregation.append(average)
            data = {'rows': rows, 'aggregation': aggregation}
        response_object = construct_response(code, title, message, data)
        return response_object
    except DatabaseError:
        code = 2001
        title = 'Sorry, error occurred in database operations'
        message = 'Sorry, error occurred in database operations'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except OperationalError:
        code = 2011
        title = 'Sorry, operational error occurred'
        message = 'Sorry, operational error occurred'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object
    except:
        code = 2021
        title = 'Sorry, error occurred at the server'
        message = 'Sorry, error occurred at the server'
        data = {} 
        response_object = construct_response(code, title, message, data)
        return response_object




@csrf_exempt
def get_page_data_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        if not role:
            code = 2031
            title = 'Sorry, you have to login to perform this action'
            message = 'Sorry, you have to login to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            print(response_object)
            return HttpResponse(response_object)

        else:
            data = json.loads(request.body)
            start_timestamp = data.get('startTimestamp', '').strip()
            end_timeStamp = data.get('endTimeStamp', '').strip()
            topic_id = data.get('topicId', -2)
            parent_level = data.get('parentLevel', -1)
            parent_id = data.get('parentId', -1)
            parent_id = data.get('parentId', -1)
            channel_id = data.get('channelId', -1)
            response_object= get_page_data(parent_id, parent_level, topic_id, end_timeStamp, start_timestamp) 
            print(response_object)
            return HttpResponse(response_object)

#@login_required
@csrf_exempt
def get_topics(request):
    if request.method == 'POST':
        topics = Content.objects.filter(topic_id='').first()
        obj = json.loads(topics.sub_topics)
        wrap = {}
        wrap['topic'] = obj
        response = construct_response(0, '', '', wrap);
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')
    else:
        response = construct_response(1111,'wrong request','wrong request','')
        response_text = serializers.serialize('json',response)
        return HttpResponse(response_text,content_type='application/json')

#@login_required
@csrf_exempt
def get_trend(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        params = json.loads(body_unicode)
        start_timestamp = params['startTimestamp']
        start = datetime.datetime.fromtimestamp(start_timestamp)
        end_timestamp = params['endTimestamp']
        end = datetime.datetime.fromtimestamp(end_timestamp)
        topic_id = params['contentId']
        channel_id = params['channelId']
        level = params['level']
        item_id = params['itemId']
        data = None
        if level == -1 or level == 0:
            pass
        elif level == 1:
            data = MasteryLevelSchool.objects.filter(school_id=item_id, content_id=topic_id, channel_id=channel_id,\
                date__gt=start_timestamp,date__lt=end_timestamp).order_by('date')
        elif level == 2:
            data = MasteryLevelClass.objects.filter(class_id=item_id, content_id=topic_id, channel_id=channel_id,\
                date__gt=start_timestamp,date__lt=end_timestamp).order_by('date')
        elif level == 3:
            data = MasteryLevelStudent.objects.filter(student_id=item_id, content_id=topic_id, channel_id=channel_id,\
                date__gt=start,date__lt=end).order_by('date')
        res = {}
        series = []
        series.append({'name':'percentage of exercise completed','isPercentage':True})
        series.append({'name':'percentage of exercise correct','isPercentage':True})
        series.append({'name':'# attemps','isPercentage':False})
        series.append({'name':'completed students','isPercentage':False})
        points = []
        for ele in data:
            temp = []
            temp.append(time.mktime(ele.date.timetuple()))
            temp.append(ele.completed_questions)
            temp.append(ele.correct_questions)
            temp.append(ele.attempt_questions)
            if level == 3:
                temp.append(ele.completed)
            else:
                temp.append(ele.students_completed)
            points.append(temp)
        res['series'] = series
        res['points'] = points
        #data_str = serializers.serialize('json', data)
        response = construct_response(0,'','',res)
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')
    else:
        response = construct_response(1111,'wrong request','wrong request','')
        response_text = serializers.serialize('json',response)
        return HttpResponse(response_text,content_type='application/json')

@csrf_exempt
def get_report_mastery(request):
    if request.method == 'GET':
        return render(request,'report-mastery.html')
    else:
        return HttpResponse()













