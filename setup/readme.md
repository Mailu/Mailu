## Adding more flavors/steps
(Everything will go under setup/ directory - using Kubernetes flavor as example)

Until this point, the app is working as it follows:
- when accesing the setup page it will display the flavors selection step (`templates/steps/flavor.html`)
- after you choose your desired flavor it will iterare over the files in the flavor directory and building the page
  (`templates/steps/config.html is general for all flavors`)
- when you complete all required fields and press "Setup Mailu" button it will redirect you to the setup page (`flavors/choosen-flavor/setup.html`)
  
To add a new flavor you need to create a directory under `templates/steps/` in which you are adding actual steps.
Eg: Adding a WIP step we'll create `templates/steps/kubernetes/wip.html`

*Note that wizard.html is iterating over files in this directory and building the page. Files are prefixed with a number for sorting purposes.*

wip.html will start with

```
{% call macros.panel("info", "Step X - Work in progress")
``` 

and end with 
```
{% endcall %}
```

You store variable from front-page using the name attribute inside tag.
In the example below the string entered in the input field is stored in the variable `named var_test`
```
<input type="text" name="var_test">
```

In order to user the variable furter you use it like `{{ var_test }}`

In the setup page (`flavors/kubernetes/setup`) you cand add steps by importing macros

```
{% import "macros.html" as macros %}
```

and start and end every step with
```
{% call macros.panel("info", "Step X - Title") %}
-------------------
{% endcall %}
```

