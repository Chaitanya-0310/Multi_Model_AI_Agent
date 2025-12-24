# Try the modern import first
try:
    from langchain_core.prompts import PromptTemplate
    print("Success: Imported from langchain_core")
except ImportError:
    # Fallback for older versions
    from langchain.prompts import PromptTemplate
    print("Success: Imported from langchain.prompts")

template = PromptTemplate.from_template("Hello {name}")
print(template.format(name="World"))