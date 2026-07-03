import json
import os
import re

def version_bump(repo_path, package, fix_version, ecosystem):
    if not package or not fix_version or not ecosystem:
        return False
    
    if(ecosystem=="npm"):
        with open(os.path.join(repo_path, 'package.json'), 'r') as jsonfile:
            data = json.load(jsonfile)
        
        found = False

        if(package in data.get("dependencies", {})):   
            data["dependencies"][package] = fix_version
            found = True
           
        if(package in data.get("devDependencies", {})):
            data["devDependencies"][package] = fix_version
            found = True

        if found:
            with open(os.path.join(repo_path, 'package.json'), 'w') as file:
                json.dump(data, file, indent = 4)
                return True
        return False
                
    elif(ecosystem=="pip"):
        with open(os.path.join(repo_path, 'requirements.txt'), 'r') as pipfile:
            data = pipfile.readlines()

        newdata = []
        foundPackage = False
        for line in data:
            if(re.match(rf"^{package}[=><]", line)):
                newdata.append(f"{package}=={fix_version}\n")
                foundPackage = True
            else:
                newdata.append(line)

        if not foundPackage:
            return False

        with open(os.path.join(repo_path, 'requirements.txt'), 'w') as pipwrite:
            pipwrite.writelines(newdata)

        return True
    
    else:  
        return False

    