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
from django.db.models import Sum
import json
import datetime
import time

# This function contructs the dict for every response 
# code = 0 represents that the processing is sucessful
def construct_response(code, title, message, data):
    response_object = {}
    response_object["code"] = code
    response_object["info"] = {"title": title,"message": message}
    response_object["data"] = data
    return response_object            

# This function implements the logic for login 
def login_post(username, password):
    #try:
        is_success = False
        code = 0
        role = -1
        title = ""
        message = ""
        data = {}
        # If both username and password are not null or empty
        if username and password:     
            # Find if user with corresponding username and password exists
            result = Users.objects.filter(username=username).filter(password=password)
            # If not, note that the combination is not found 
            if not result:
                code = 1001
                title = 'The username/password combination used was not found on the system'
                message = 'The username/password combination is incorrect'
                data = {'username': username} 
                user = Users.objects.filter(username=username)
                # If the role_id is not 4 (which means that the user is an admin), increase the number of failed attempts
                # If the user has wrongfully input the password for 4 times, block the user
                if user and user[0].role_id != 4:
                    user[0].number_of_failed_attempts += 1
                    if user[0].number_of_failed_attempts >= 4:
                        user[0].is_active = False
                    user[0].save()
            # If the combination exists, check if the user has been blocked
            else:
                # If the user has wrongfully input password for 4 or more than 4 times 
                if result[0].role_id != 4:
                    if result[0].number_of_failed_attempts >= 4:
                        # Notify the user that he has been blocked
                        code = 1002
                        title = 'Sorry, you have been blocked'
                        message = 'The user has been blocked'
                        data = {'username': username} 
                    # If the user has not been blocked
                    else:
                        mappings = UserRoleCollectionMapping.objects.filter(user_id = result[0]).filter(is_approved=True)
                        if mappings:
                            result[0].number_of_failed_attempts = 0
                            result[0].last_login_time = timezone.now()
                            result[0].save()
                            role = result[0].role_id
                            is_success = True  
                        else:
                            code = 1004
                            title = 'Sorry, you have not been approved yet'
                            message = 'Sorry, you have not been approved yet' 
                            data = {'username': username} 
                            is_success = False
                else:
                    role = 4
                    is_success = True

        # If either the username/password is empty
        else:
            # Notify the user that the input info is not complete
            code = 1003
            title = 'The username/password are required'
            message = 'The username/password are required'
            data = {'username': username}
            is_success = False
        response_object = construct_response(code, title, message, data)
        return response_object, is_success, role
    # If exception occurred, construct corresponding error info to the user
'''
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
'''
    


# This function implements the request receiving and response sending for login 
@csrf_exempt
def login_view(request):
    # If GET request is received, render the login page 
    if request.method == 'GET':
        code = 0
        title = ""
        message = ""
        data = {}
        response_object = construct_response(code, title, message, data)
        return render(request, 'login.html', response_object)
    # If POST request is received, call login_post function to process    
    elif request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        response_object, is_success, role = login_post(username, password)
        
        # If login is successful, the report page is rendered 
        if is_success:
            response = redirect(reverse('report'))
            response.set_cookie('role', role)
        # If login fails, return HttpResponse in JSON format
        else:    
            response = render(request, 'login.html', response_object) 
            
            response.delete_cookie('role')
        response.delete_cookie('username')
        return response
    else:
        return HttpResponse()


# This function implements the request receiving and response sending for logout
@csrf_exempt
def logout_view(request):
    # If GET request is received, render the index page 
    if request.method == 'GET':
        try:
            logout(request)
            code = 0
            title = ""
            message = ""
            data = {}
            response_object = construct_response(code, title, message, data)
            response = render(request, 'login.html', response_object)
            # Clear the cookie
            response.delete_cookie('role')
            return response
        except:
            code = 2021
            title = 'Sorry, error occurred at the server'
            message = 'Sorry, error occurred at the server'
            data = {} 
            response_object = construct_response(code, title, message, data)
            response_text = json.dumps(response_object,ensure_ascii=False)
            return render(request, 'login.html', response_object)
            #return HttpResponse(response_text,content_type='application/json')
    else:
        return HttpResponse()

# This function gets all schools and classes in the database
def get_school_and_classes():
    institutes = []
    school_info = {}
    school_id = ''
    school_name = ''
    school = UserInfoSchool.objects.all()
    # Get all the schools, if schools exist
    if school:
        for i in range(0, len(school)):
            # For each school, get the id and name
            school_id = school[i].school_id
            school_name = school[i].school_name
            classes_array = []
            # Get all the calsses under a school
            classes_in_school = UserInfoClass.objects.filter(parent=school_id)
            if classes_in_school:
                for i in range(0, len(classes_in_school)):
                    current_class = {'name': classes_in_school[i].class_name, 'id': str(classes_in_school[i].class_id)}
                    classes_array.append(current_class)
            # Construct the response object
            school_info = {'name': school_name, 'id': str(school_id), 'classes': classes_array}
            institutes.append(school_info)
    return institutes
 

        
# This function implements the logic for logout
@csrf_exempt
def register_post(username, password, first_name, last_name, email, role_id, institute_id, classes): 
    try:
        not_complete = False
        username_exists = False
        is_success = False
        # Check if all the needed info is complete 
        if (not username) or (not password) or (not email) or (not role_id) or role_id == '0' or (not first_name) or (not last_name):
            not_complete = True
        # If the user is a school leader(2) or a teacher(3), an institute_id is needed 
        if (role_id == '2' or role_id == '3') and (not institute_id):
            not_complete = True
        # If the user is a teacher(3), an institute_id is needed 
        if role_id == '3' and (not classes):
            not_complete = True

        # If info is complete, check if the username has exists (username cannot be duplicate)
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
        # If the info is not complete or username has existed, the registration fails
        if not_complete or username_exists:
            autoComplete = {'username': username, 'firstName': first_name, 'lastName': last_name, 'email': email, 'role': role_id, 'instituteId': institute_id, 'classes': classes}
            institutes = get_school_and_classes()
            data = {'autoComplete': autoComplete, 'institutes': institutes}   
            is_success = False
        # If the registration successed 
        else:
            number_of_failed_attempts = 0
            create_date = timezone.now()
            new_user = Users(username=username, password=password, first_name=first_name, last_name=last_name, email=email, number_of_failed_attempts=number_of_failed_attempts, create_date=create_date, role_id=role_id)
            new_user.save()
            # If the user is board member
            if role_id == 1:
                user_role_collection_mapping = UserRoleCollectionMapping(user_id=new_user)
                user_role_collection_mapping.save()
            # If the user is a school leader, add school into the user mapping 
            elif role_id == 2:
                school = UserInfoSchool.objects.filter(school_id=int(institute_id))
                if school:
                    user_role_collection_mapping = UserRoleCollectionMapping(user_id=new_user, institute_id=school[0])
                    user_role_collection_mapping.save()
            # If the user is a teacher, add school and classes into the user mapping 
            elif role_id == 3:
                school = UserInfoSchool.objects.filter(school_id=int(institute_id))
                if school:
                    for i in range(0, len(classes)):
                        current_class = UserInfoClass.objects.filter(class_id=int(classes[i]))
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
    # If exception occurred, construct corresponding error info to the user
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

# This function implements the request receiving and response sending for register
@csrf_exempt
def register_view(request):
    # If GET request is received, render the register page, return the school and class info
    if request.method == 'GET':
        institutes = get_school_and_classes()
        data = {'institutes': institutes}   
        code = 0
        title = ''
        message = ''
        response_object = construct_response(code, title, message, data)
        response_text = json.dumps(response_object,ensure_ascii=False)
        response_str = json.loads(response_text)
        return render(request, 'register.html', {'data':response_str})  

    # If POST request is received, process the request and return JSON object
    elif request.method == 'POST':
        
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)


        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        email = data.get('email', '').strip()
        role_id = str(data.get('role', '')).strip()
        institute_id = str(data.get('instituteId', '')).strip()
        classes = data.get('classes', [])
        
        response_object, is_success = register_post(username, password, first_name, last_name, email, role_id, institute_id, classes)
        
        
        response_text = json.dumps(response_object,ensure_ascii=False)
        response = HttpResponse(response_text)
        
        return response
    else:
        return HttpResponse()

    

 
# This function implements the logic for admin approve users
def admin_approve_pending_users_post(users):
    try:
        code = 0
        title = ''
        message = ''
        data = {}
        # If the users to be approved is not empty
        if len(users) != 0:
            for i in range(len(users)):
                username = users[i]["username"]
                result = Users.objects.filter(username=username)
                if result:
                    # Mark the user as active
                    result[0].is_active = True
                    result[0].update_date = timezone.now()
                    result[0].save()
                    # If the user is a board memeber or leader, only one mapping exists
                    if result[0].role_id == 1 or result[0].role_id == 2:
                        mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0])
                        if mapping:
                            mapping[0].is_approved = True
                            
                            mapping[0].save()
                    # If the user is a teacher, multiple mappings to the classrooms exist
                    elif result[0].role_id == 3:
                        classes = users[i]["classes"]
                        for j in range(len(classes)):
                            approve_class = UserInfoClass.objects.filter(class_id = classes[j])
                            if approve_class:
                                mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0]).filter(class_id=approve_class[0])
                                if mapping:
                                    mapping[0].is_approved = True
                                   
                                    mapping[0].save()
        response_object = construct_response(code, title, message, data) 
       
        return response_object
    # If exception occurred, construct corresponding error info to the user
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



# This function implements the request receiving and response sending for admin approve users   
@csrf_exempt
def admin_approve_pending_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        # If the user is not an admin
        if role != '4':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            print(response_object)
        # If the user is an admin, process the request
        else:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            users = data.get('users',[])      
            response_object = admin_approve_pending_users_post(users)
            print(response_object)

        response_text = json.dumps(response_object,ensure_ascii=False)
        return HttpResponse(response_text)
    else:
        return HttpResponse()

# This function implements the logic for admin disapprove users
def admin_disapprove_pending_users_post(users): 
    code = 0
    title = ''
    message = ''
    data = {}
    try:
        if users:
            # If the users to be disapproved is not empty
            for i in range(len(users)):
                username = users[i]['username']
                result = Users.objects.filter(username=username)
                if result:
                    result[0].update_date = timezone.now()
                    result[0].save()
                    # If the user is a board memeber or leader, only one mapping exists, delete the mapping 
                    if result[0].role_id == 1 or result[0].role_id == 2:
                        mapping = UserRoleCollectionMapping.objects.filter(user_id=result[0])
                        if mapping:
                           
                            mapping[0].delete()
                            
                    # If the user is a teacher, multiple mappings to the classrooms exist. Delete all the mappings       
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
    # If exception occurred, construct corresponding error info to the user
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

# This function implements the request receiving and response sending for admin approve users   
@csrf_exempt
def admin_disapprove_pending_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        # If the user is not an admin
        if role != '4':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            print(response_object)
        # If the user is an admin, process the request
        else:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            users = data.get('users',[])       
            print("users = ", users)
            response_object = admin_disapprove_pending_users_post(users)
            print(response_object)
        response_text = json.dumps(response_object,ensure_ascii=False)

        return HttpResponse(response_text)
    else:
        return HttpResponse()
    
# This function implements the logic for admin unblock users
def admin_unblock_users_post(usernames):
    code = 0
    title = ''
    message = ''
    data = {}
    try:
        if usernames:
            for i in range(len(usernames)):
                # Check if the username exists
                username = usernames[i]
                result = Users.objects.filter(username=username)
                # If exists, change is_active to True, and clear the number_of_failed_attempts
                if result:
                    result[0].is_active = True;
                    result[0].number_of_failed_attempts = 0;
                    result[0].update_date = timezone.now()
            
                    result[0].save()
        response_object = construct_response(code, title, message, data) 
        return response_object
    # If exception occurred, construct corresponding error info to the user
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



# This function implements the request receiving and response sending for admin unblock users       
@csrf_exempt
def admin_unblock_users_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        # If the user is not an admin
        if role != '4':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)

        # If the user is an admin, process the request
        else:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            usernames = data.get('usernames',[])
            response_object = admin_unblock_users_post(usernames)
        print(response_object)
        response_text = json.dumps(response_object,ensure_ascii=False)
        return HttpResponse(response_text)
    else:
        return HttpResponse()

# This function implements the logic for admin get pending and blocked users
def admin_get_post():
    try:
        code = 0
        title = ''
        message = ''
        pending_users = []
        blocked_users = []
        # Get users that has not been approved
        pendings = UserRoleCollectionMapping.objects.filter(is_approved = False)
        if pendings:
            for pending in pendings:
                # Find the user according to user_id
                user = pending.user_id
                if not user:
                    continue
                curr_class = pending.class_id
                institute = pending.institute_id
                instituteId = -1
                classId = -1
                instituteName = ''
                className = ''
                
                username = user.username
                email = user.email
                role = user.role_id
                # Find corresponding class and school
                if curr_class:
                    className = curr_class.class_name
                    classId = curr_class.class_id
                if institute:
                    instituteId = institute.school_id
                    instituteName = institute.school_name
                pending_user = {'username': username, 'email': email, 'role': role, 'instituteId': instituteId, 'instituteName': instituteName, 'classId': classId, 'className': className}
                pending_users.append(pending_user)

        # Get users that has not been blocked
        blockeds = Users.objects.filter(is_active = False)
        if blockeds:
            for blocked in blockeds:
                username = blocked.username
                email = blocked.email
                role = blocked.role_id
                # Find the mapping according to user_id
                mappings = UserRoleCollectionMapping.objects.filter(user_id = blocked)
                # If corresponding mapping exists 
                if mappings:
                    for mapping in mappings:
                        instituteId = -1
                        classId = -1
                        instituteName = ''
                        className = ''

                        institute = mapping.institute_id
                        # Find the schools and classes
                        if institute:
                            instituteId = institute.school_id
                            instituteName = institute.school_name
                        curr_class = mapping.class_id
                        if curr_class:
                            className = curr_class.class_name
                            classId = curr_class.class_id
                        blocked_user = {'username': username, 'email': email, 'role': role, 'instituteId': instituteId, 'instituteName': instituteName, 'classId': classId, 'className': className}
                        blocked_users.append(blocked_user)
                # If corresponding mapping doesn't exist, put instituteId and classId as -1
                else:
                    blocked_user = {'username': username, 'email': email, 'role': role, 'instituteId': -1, 'instituteName': '', 'classId': -1, 'className': ''}
                    blocked_users.append(blocked_user)

        data = {'pendingUsers': pending_users, 'blockedUsers': blocked_users}
        response_object = construct_response(code, title, message, data) 
        return response_object
    # If exception occurred, construct corresponding error info to the user
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


# This function implements the request receiving and response sending for admin get pending and blocked users
@csrf_exempt
def admin_get_view(request):
    if request.method == 'GET':
        role = request.COOKIES.get('role')
        # If user is not an admin
        if role != '4':
            code = 2031
            title = 'Sorry, you have to be admin to perform this action'
            message = 'Sorry, you have to be admin to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
         # If user is an admin, render the admin-users page
        else:
            response_object = admin_get_post()
        return render(request, 'admin-users.html', response_object)
    else:
        return HttpResponse()



# This function implements the request receiving and response sending for rending report homepage
@csrf_exempt
def report_homepage_view(request):
    if request.method == 'GET':
        role = request.COOKIES.get('role')
        # If the user has not logged in
        if not role:
            code = 0
            title = ''
            message = ''
            data = {}

            #response_text = json.dumps(response_object,ensure_ascii=False)
            response_object = construct_response(code, title, message, data)
            return render(request, 'login.html', response_object)

        # If the user has logged in, render the index page
        else:
            code = 0
            title = ''
            message = ''
            try:
                latest_date = LatestFetchDate.objects.filter()

                if latest_date:
                    data = {'dateUpdated': latest_date[0].latest_date}
                else:
                    data = {}
                response_object = construct_response(code, title, message, data)
                return render(request, 'index.html', response_object)
            # If exception occurred, construct corresponding error info to the user
            except DatabaseError:
                code = 2001
                title = 'Sorry, error occurred in database operations'
                message = 'Sorry, error occurred in database operations'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'index.html', response_object)
            except OperationalError:
                code = 2011
                title = 'Sorry, operational error occurred'
                message = 'Sorry, operational error occurred'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'index.html', response_object)
            except:
                code = 2021
                title = 'Sorry, error occurred at the server'
                message = 'Sorry, error occurred at the server'
                data = {} 
                response_object = construct_response(code, title, message, data)
                return render(request, 'index.html', response_object)
    else:
        return HttpResponse()


     
# Construct the breadcrumb format 
def construct_breadcrumb(parentName, parentLevel, parentId):
    res = {
        "parentName": parentName,
        "parentLevel": parentLevel,
        "parentId": parentId
        }

    return res
# Construct the metrics format 
def construct_metrics():
    metrics = [
        {'displayName': '% exercise completed', 'toolTip': ''},
        {'displayName': '% exercise correct', 'toolTip': ''},
        {'displayName': '# attempts completed', 'toolTip': ''},
        {'displayName': '% students completed the topic', 'toolTip': ''},
    ]
    return metrics

# This function implements the logic for get page meta
def get_page_meta(parent_id, parent_level):
    try:
        code = 0
        title = ''
        message = ''
        # If the parent_level and parent_id info is not complete
        if parent_level == -1 or parent_id == -2:
            code = 2031
            title = 'Parent level or parent id is missing'
            message = 'Parent level or parent id is missing'
            data = {} 
         # If the parent_level and parent_id info is complete
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
                            "id": str(school.school_id),
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

                    classes = UserInfoClass.objects.filter(parent = parent_id)
                    if classes:
                        for curr_class in classes:
                            temp = {
                                "id": str(curr_class.class_id),
                                "name": curr_class.class_name
                            }
                            rows.append(temp)
            # If the parent level is class
            elif parent_level == 2:
                #Add current level class to the breadcrumb
                curr_class = UserInfoClass.objects.filter(class_id = parent_id)
                if curr_class:
                    class_name = curr_class[0].class_name
                   
                #Add higher level school to the breadcrumb
                    school = UserInfoSchool.objects.filter(school_id = curr_class[0].parent).first()
                    if school:
                        school_id = str(school.school_id)
                        school_name = school.school_name
                        breadcrumb.append(construct_breadcrumb(school_name, 1, school_id))
                        breadcrumb.append(construct_breadcrumb(class_name, 2, parent_id))
                    # Return all students inside a classroom
                students = UserInfoStudent.objects.filter(parent = parent_id)
                # Return all students inside a classroom
                #students = UserInfoStudent.objects.filter(parent = curr_class[0])
                if students:
                    for student in students:
                        temp = {
                            'id': str(student.student_id),
                            'name': student.student_name
                        }
                        rows.append(temp)
            data = {'breadcrumb': breadcrumb, 'metrics': metrics, 'rows': rows}
        response_object = construct_response(code, title, message, data)
        return response_object
    # If exception occurred, construct corresponding error info to the user
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
        

# This function implements the request receiving and response sending for get page meta
@csrf_exempt
def get_page_meta_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        # If the user has not logged in
        if not role:
            code = 2031
            title = 'Sorry, you have to login to perform this action'
            message = 'Sorry, you have to login to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            response_text = json.dumps(response_object,ensure_ascii=False)
            return HttpResponse(response_text,content_type='application/json')
         # If the user has logged in, response in JSON format
        else:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            parent_level = data.get('parentLevel', -2)
            parent_id = int(data.get('parentId', '').strip())
            response_object= get_page_meta(parent_id, parent_level) 
            response_text = json.dumps(response_object,ensure_ascii=False)
            return HttpResponse(response_text,content_type='application/json')
          
            
    else:
        return HttpResponse()
        
# This function implements the logic for get page data        
def get_page_data(parent_id, parent_level, topic_id, end_timestamp, start_timestamp, channel_id):
    #try:
        code = 0
        title = ''
        message = ''
        data = {}
        # If the input data is not complete
        if parent_level == -1 or parent_id == -2 or topic_id == '' or (not start_timestamp) or (not end_timestamp) or channel_id == '':
            code = 2031
            title = 'Argument is missing'
            message = 'Argument is missing'
            data = {} 
        # If the input data is complete
        else: 
            rows = []
            aggregation = []
            percent_complete_array = []
            percent_correct_array = []
            number_of_attempts_array = []
            percent_student_completed_array = []

            values = []
            total_questions = 0
            # Since in django select range function, the end_date is not included, hence increase the date by one day
            end_timestamp = str(int(end_timestamp) + 86400)
            # Convert from Unix timestamp to datetime
            start_timestamp = datetime.date.fromtimestamp(int(start_timestamp)).strftime('%Y-%m-%d')
            end_timestamp = datetime.date.fromtimestamp(int(end_timestamp)).strftime('%Y-%m-%d')
            # If the user wants to view everything
            if topic_id == '-1' and channel_id == '-1':
                topic = Content.objects.filter(topic_id = "").first()  
            # If the user has specified content_id and channel_id
            else:
                topic = Content.objects.filter(topic_id=topic_id).filter(channel_id = channel_id).first()

            if topic:
                total_questions = topic.total_questions




            # If the current level is root
            if parent_level == 0:
                # Return all the schools 
                schools = UserInfoSchool.objects.all()
                # For each school, calculate
                if schools:
                    for school in schools:  
                        # Get school id and name
                        school_id = str(school.school_id)
                        school_name = school.school_name
                        completed_questions = 0
                        correct_questions = 0
                        number_of_attempts = 0
                        students_completed = 0
                        total_students = 0 


                        # Filter all mastery level logs belong to a certain school within certain time range
                        if topic_id == '-1':
                            mastery_schools = MasteryLevelSchool.objects.filter(school_id=school).filter(content_id="").filter(date__range=(start_timestamp, end_timestamp))
                        else:
                             mastery_schools = MasteryLevelSchool.objects.filter(school_id=school).filter(channel_id=channel_id).filter(content_id=topic_id).filter(date__range=(start_timestamp, end_timestamp))
                        if mastery_schools:
                           
                            for mastery_school in mastery_schools:
                                completed_questions += mastery_school.completed_questions
                                correct_questions += mastery_school.correct_questions
                                number_of_attempts += mastery_school.attempt_questions
                                students_completed += mastery_school.students_completed
                                
                       
                                


                        total_students = school.total_students
                        if total_questions == 0 or total_students == 0:
                            values = ["0.00%", "0.00%", 0, "0.00%"]
                            row = {'id': school_id, 'name': school_name, 'values': values}
                            rows.append(row)
                            continue
                        
                      
                        # Calculate the percentage of completed questions
                        percent_complete_float = float(completed_questions) / (total_questions * total_students)
                        percent_complete = "{0:.2%}".format(percent_complete_float)
                        percent_complete_array.append(percent_complete_float)
                    
                        # Calculate the percentage of correct questions
                        
                        percent_correct_float = float(correct_questions) / (total_questions * total_students)
                        percent_correct = "{0:.2%}".format(percent_correct_float)
                        percent_correct_array.append(percent_correct_float)

                        # Get the number of attempted questions
                        
                        number_of_attempts_array.append(number_of_attempts)

                        # Calculate the percentage of students completed the topic
                        
                        percent_student_completed_float = float(students_completed) / (total_students * total_questions)
                        percent_student_completed = "{0:.2%}".format(percent_student_completed_float)
                        percent_student_completed_array.append(percent_student_completed_float)

                        values = [percent_complete, percent_correct, number_of_attempts, percent_student_completed]
                        row = {'id': school_id, 'name': school_name, 'values': values}
                        rows.append(row)

            # If the parent level is school
            elif parent_level == 1:
                # Find the current school
                school = UserInfoSchool.objects.filter(school_id = parent_id)
               
                # Return all the classrooms inside a school
                if school:
                    classes = UserInfoClass.objects.filter(parent = parent_id)
                    if classes:
                        for curr_class in classes:
                            # Get class id and name
                            class_id = str(curr_class.class_id)
                            class_name = curr_class.class_name
                            completed_questions = 0
                            correct_questions = 0
                            number_of_attempts = 0
                            students_completed = 0
                            total_students = 0 


                            # Filter all mastery level logs belongs to a certain class within certain time range
                            if topic_id == '-1':
                                mastery_classes = MasteryLevelClass.objects.filter(class_id=curr_class).filter(content_id="").filter(date__range=(start_timestamp, end_timestamp))
                            else:
                                 mastery_classes = MasteryLevelClass.objects.filter(class_id=curr_class).filter(channel_id=channel_id).filter(content_id=topic_id).filter(date__range=(start_timestamp, end_timestamp))

                            if mastery_classes:
                                for mastery_class in mastery_classes:
                                    completed_questions += mastery_class.completed_questions
                                    correct_questions += mastery_class.correct_questions
                                    number_of_attempts += mastery_class.attempt_questions
                                    students_completed += mastery_class.students_completed
                                    
                            # Filter mastery level belongs to a certain class with certain topic id, and within certain time range
                            

                            total_students = curr_class.total_students
                            if total_questions == 0 or total_students == 0:
                                values = ["0.00%", "0.00%", 0, "0.00%"]
                                row = {'id': class_id, 'name': class_name, 'values': values}
                                rows.append(row)
                                continue

                            # Calculate the percentage of completed questions
                            percent_complete_float = float(completed_questions) / (total_questions * total_students)
                            percent_complete = "{0:.2%}".format(percent_complete_float)
                            percent_complete_array.append(percent_complete_float)
                        
                            # Calculate the percentage of correct questions
                            
                            percent_correct_float = float(correct_questions) / (total_questions * total_students)
                            percent_correct = "{0:.2%}".format(percent_correct_float)
                            percent_correct_array.append(percent_correct_float)

                            # Get the number of attempted questions
                            
                            number_of_attempts_array.append(number_of_attempts)

                            # Calculate the percentage of students completed the topic
                            
                            percent_student_completed_float = float(students_completed) / (total_students * total_questions)
                            percent_student_completed = "{0:.2%}".format(percent_student_completed_float)
                            percent_student_completed_array.append(percent_student_completed_float)

                            values = [percent_complete, percent_correct, number_of_attempts, percent_student_completed]
                            row = {'id': class_id, 'name': class_name, 'values': values}
                            rows.append(row)


            # If the parent level is class
            elif parent_level == 2:
                curr_class = UserInfoClass.objects.filter(class_id = parent_id)
                # Return all the students inside a class
                if curr_class:
                    students = UserInfoStudent.objects.filter(parent = parent_id)
                    if students:
                        for student in students:
                            # Get class id and name
                            student_id = str(student.student_id)
                            # Get student id and name
                        
                            student_name = student.student_name
                            completed_questions = 0
                            correct_questions = 0
                            number_of_attempts = 0
                            number_of_content = 0 
                            completed = True
                     
                           


                            # Filter mastery level belongs to a certain student within certain time range
                            if topic_id == '-1':
                                mastery_students = MasteryLevelStudent.objects.filter(student_id=student).filter(content_id="").filter(date__range=(start_timestamp, end_timestamp))
                            else:
                                mastery_students = MasteryLevelStudent.objects.filter(student_id=student).filter(channel_id=channel_id).filter(content_id=topic_id).filter(date__range=(start_timestamp, end_timestamp))
                                
                                   
                            # Filter mastery level belongs to a certain student with certain topic id, and within certain time range
                            
                            if mastery_students:    
                                for mastery_student in mastery_students:
                                    completed_questions += mastery_student.completed_questions
                                    correct_questions += mastery_student.correct_questions
                                    number_of_attempts += mastery_student.attempt_questions
                                    if completed:
                                        completed = mastery_student.completed and completed
                         
                 
                            if len(mastery_students) == 0:
                                values = ["0.00%", "0.00%", 0, "0.00%"]
                                row = {'id': student_id, 'name': student_name, 'values': values}
                                rows.append(row)
                                continue
                                
                            # Calculate the percentage of completed questions
                            percent_complete_float = float(completed_questions) / total_questions
                            percent_complete = "{0:.2%}".format(percent_complete_float)
                            percent_complete_array.append(percent_complete_float)
                        
                            # Calculate the percentage of correct questions
                            
                            percent_correct_float = float(correct_questions) / total_questions 
                            percent_correct = "{0:.2%}".format(percent_correct_float)
                            percent_correct_array.append(percent_correct_float)

                            # Get the number of attempted questions
                            
                            number_of_attempts_array.append(number_of_attempts)

                            # Calculate the percentage of students completed the topic
                            
                            if completed:
                                completed = "100.00%"
                                percent_student_completed_array.append("100%")
                            else:
                                completed = "0.00%"
                                percent_student_completed_array.append("0%")

                            values = [percent_complete, percent_correct, number_of_attempts, completed]
                            row = {'id': student_id, 'name': student_name, 'values': values}
                            rows.append(row)
            avg_percent_complete = 0
            avg_percent_correct = 0
            avg_number_of_attempts = 0
            avg_percent_student_completed = 0


            # Calculate the average for these four metrics
            length = len(percent_complete_array)
            if length != 0:
                for i in range(length):
                    avg_percent_complete +=  percent_complete_array[i]
                    avg_percent_correct += percent_correct_array[i]
                    avg_number_of_attempts += number_of_attempts_array[i]
                    if parent_level != 2:
                        avg_percent_student_completed += percent_student_completed_array[i]
                avg_percent_complete /= length
                avg_percent_correct /= length
                avg_number_of_attempts /= length
                if parent_level == 2:
                    avg_percent_student_completed = ""
                else:
                     avg_percent_student_completed /= length
                     avg_percent_student_completed = "{0:.2%}".format(avg_percent_student_completed)
                values = ["{0:.2%}".format(avg_percent_complete), "{0:.2%}".format(avg_percent_correct), str(int(avg_number_of_attempts)), avg_percent_student_completed]
                average = {'name': 'Average', 'values': values}
                aggregation.append(average)
            data = {'rows': rows, 'aggregation': aggregation}
        response_object = construct_response(code, title, message, data)
        
        return response_object
    # If exception occurred, construct corresponding error info to the user
'''
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
'''
        



# This function implements the request receiving and response sending for get page data
@csrf_exempt
def get_page_data_view(request):
    if request.method == 'POST':
        role = request.COOKIES.get('role')
        # If the user has not logged in
        if not role:
            code = 2031
            title = 'Sorry, you have to login to perform this action'
            message = 'Sorry, you have to login to perform this action'
            data = {} 
            response_object = construct_response(code, title, message, data)
            response_text = json.dumps(response_object,ensure_ascii=False)
            return HttpResponse(response_text,content_type='application/json')
        # If the user has logged in, process the request
        else:
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)
            start_timestamp = data.get('startTimestamp', 0)
            end_timestamp = data.get('endTimestamp', 0)
            topic_id = data.get('contentId', '').strip()
            parent_level = data.get('parentLevel', -1)
            parent_id = int(data.get('parentId', '').strip())
            channel_id = data.get('channelId', '').strip()
            response_object= get_page_data(parent_id, parent_level, topic_id, end_timestamp, start_timestamp, channel_id) 
            response_text = json.dumps(response_object,ensure_ascii=False)
            print(response_text)
            return HttpResponse(response_text,content_type='application/json')
           
    else:
        return HttpResponse()

#@login_required
@csrf_exempt
def get_topics(request):
    if request.method == 'POST':
        topics = Content.objects.filter(topic_id='').first()
        obj = json.loads(topics.sub_topics)
        response = construct_response(0, '', '', obj);
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')
    else:
        response = construct_response(1111,'wrong request','wrong request','')
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')

#@login_required
@csrf_exempt
def get_trend(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        params = json.loads(body_unicode)
        start_timestamp = params.get('startTimestamp','')
        start = datetime.datetime.fromtimestamp(start_timestamp)
        end_timestamp = params.get('endTimestamp', '')
        end = datetime.datetime.fromtimestamp(end_timestamp)
        topic_id = params.get('contentId')
        channel_id = params.get('channelId')
        level =params.get('level')
        item_id = params.get('itemId')
        data = None
        content = None
        if topic_id=="-1":
            content = Content.objects.filter(topic_id='').first()
        else:
            content = Content.objects.filter(topic_id=topic_id,channel_id=channel_id).first()
        total_questions = content.total_questions
        print(total_questions)
        total_students = 1.0
        if level == -1 or level == 0:
            pass
        elif level == 1:
            school = UserInfoSchool.objects.filter(school_id=item_id).first()
            total_students = school.total_students
            if topic_id == "-1":
                '''data = MasteryLevelSchool.objects.filter(school_id=item_id).filter(date__gt=start).filter(date__lt=end).values('channel_id')\
                .annotate(Sum('completed_questions'),Sum('correct_questions'),Sum('attempt_questions'),Sum('students_completed')).order_by('date')
                print(data)'''
                data = MasteryLevelSchool.objects.filter(school_id=item_id,content_id="",date__gte=start,date__lte=end).order_by('date')
            else:
                data = MasteryLevelSchool.objects.filter(school_id=item_id,content_id=topic_id, channel_id=channel_id,\
                    date__gte=start,date__lte=end).order_by('date')
                print(data)
        elif level == 2:
            classroom = UserInfoClass.objects.filter(class_id=item_id).first()
            total_students = classroom.total_students
            if topic_id == "-1":
                data = MasteryLevelClass.objects.filter(class_id=item_id,content_id="",date__gte=start,date__lte=end).order_by('date')
            else:
                data = MasteryLevelClass.objects.filter(class_id=item_id, content_id=topic_id, channel_id=channel_id,\
                    date__gte=start,date__lte=end).order_by('date')
        elif level == 3:
            if topic_id == "-1":
                data = MasteryLevelStudent.objects.filter(student_id=item_id,content_id="",date__gte=start,date__lte=end).order_by('date')
            else:
                data = MasteryLevelStudent.objects.filter(student_id=item_id, content_id=topic_id, channel_id=channel_id,\
                    date__gte=start,date__lte=end).order_by('date')
        res = {}
        series = []
        series.append({'name':'% exercise completed','isPercentage':True})
        series.append({'name':'% exercise correct','isPercentage':True})
        series.append({'name':'# attempts','isPercentage':False})
        series.append({'name':'% students completed topic','isPercentage':True})
        points = []
        completed_questions_sum = 0
        correct_questions_sum = 0
        attempt_questions_sum = 0
        completed_sum = 0
        for ele in data:
            temp = []
            '''if topic_id=="-1":
                completed_questions_sum += ele['completed_questions__sum']
                correct_questions_sum += ele['correct_questions__sum']
                attempt_questions_sum += ele['attempt_questions__sum']
                temp.append(time.mktime(ele['date'].timetuple()))
                temp.append(100.0*completed_questions_sum/(total_students*total_questions))
                temp.append(100.0*correct_questions_sum/(total_students*total_questions))
                temp.append(attempt_questions_sum)
                if level == 3:
                    completed_sum += ele['completed__sum']
                else:
                    completed_sum += ele['students_completed__sum']
                temp.append(100.0*completed_sum/total_students)
            else:'''
            completed_questions_sum += ele.completed_questions
            correct_questions_sum += ele.correct_questions
            attempt_questions_sum += ele.attempt_questions
            temp.append(time.mktime(ele.date.timetuple()))
            temp.append(100.0*completed_questions_sum/(total_students*total_questions))
            temp.append(100.0*correct_questions_sum/(total_students*total_questions))
            temp.append(attempt_questions_sum)
            if level == 3:
                completed_sum += ele.completed
                temp.append(completed_sum)
            else:
                completed_sum += ele.students_completed
                temp.append(completed_sum)
            points.append(temp)
        res['series'] = series
        res['points'] = points
        #data_str = serializers.serialize('json', data)
        response = construct_response(0,'','',res)
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')
    else:
        response = construct_response(1111,'wrong request','wrong request','')
        response_text = json.dumps(response,ensure_ascii=False)
        return HttpResponse(response_text,content_type='application/json')

@csrf_exempt
def get_report_mastery(request):
    print("here")
    if request.method == 'GET':
        return render(request,'report-mastery.html')
    else:
        return HttpResponse()













