---
title: Generating Application Specific Go Documentation Using Go AST and Antora
published: true
description: How to generate application specific documentation from Go code and integrate it into an Antora site.
tags: golang, documentation, showdev, html
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/bsxcmnfgzg9dy6j2b5lu.png
---

## Motivation

In one of my projects I was working on some in-house Go application to manage complex task pipelines on Kubernetes. On a high level, a task consists of one or multiple steps that are executed in order. Engineers would contribute tasks in the form of new Go files. Different teams collaborate on those tasks. Engineers running the tasks need to understand how to configure, debug and operate them correctly. Therefore, having good documentation is crucial.

The biggest challenge with documentation, however, is to keep it up-to-date. This becomes more challenging the further away the documentation is kept from the source code. In the ideal scenario, the documentation is close to the source code, e.g. in the form of [JavaDoc](https://docs.oracle.com/javase/8/docs/technotes/tools/windows/javadoc.html), [Python Docstrings](https://peps.python.org/pep-0257/), or [GoDoc](https://go.dev/blog/godoc).

The downside of these tools is that the content they generate is often tightly coupled to the ecosystem of the language. Additionally, their customizability is often limited. Typically, they generate some HTML page based on the text written in comments. Some of them will provide additional context, such as links to other packages, types, or functions. Take the JavaDoc of jvector's [`GraphIndex`](https://javadoc.io/doc/io.github.jbellis/jvector/latest/io/github/jbellis/jvector/graph/GraphIndex.html) class as an example:

![Interface GraphIndex javadoc](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/lv4aoyg95j4vbjjbylcd.png)

It shows information such as super- and implementing classes / interfaces, nested classes and implemented methods. You can browse other classes within the same package as well. This contextual information is useful, but it lacks real-world application context. Its main focus is documenting the API to other developers, and not documenting the behaviour of an application.

To make my point clearer, let's look at the type definitions for our tasks in Go. I'm going to leave out irrelevant detail here. In reality, the code is more complex. Every task has defined `TaskLogic`, which consists of one or multiple `TaskStep`s.

```go
type TaskLogic interface {
	GetSteps() []TaskStep
}
```

We support multiple types of tasks, which are mapped from their API name to the respective task logic. For the scope of this blog post, let's assume that there are two tasks: `DataProcessingTask` and `ReminderTask`.

```go
var TaskLogics = map[api.TaskType]TaskLogic{
	api.DataProcessingTask:  tasks.DataProcessingTaskLogic{},
	api.ReminderTask:        tasks.ReminderTaskLogic{},
}
```

Let's let's look into `DataProcessingTaskLogic` and the related steps in detail. Note that steps can be reused across tasks.

```go
/*
DataProcessingTaskLogic processes the provided data
in a secure and performant manner. It uses sophisticated
algorithms for maximum efficiency, while ensuring
the highest level of security through quantum-resistant encryption.
 */
type DataProcessingTaskLogic struct{}

/*
StartupStep performs the necessary startup actions,
such as initializing the database connection 
and loading the configuration.
 */
type StartupStep struct{}

/*
RunStep performs the actual data processing.
 */
type RunStep struct{}

/*
CleanupStep performs the necessary cleanup actions,
such as closing the database connection and releasing resources.
 */
type CleanupStep struct{}

func (t DataProcessingTaskLogic) GetSteps() []ot.TaskStep {
	return []ot.TaskStep{
		StartupStep{},
		RunStep{},
		CleanupStep{},
	}
}
```

Now imagine an engineer who gets alerted on a malfunctioning data processing task. The error says that the task failed in the first step. How would they know what the steps are, and what to do to debug them?

We could write that information down in a runbook but if someone updates the logic, e.g. adding a new step, the documentation in the runbook would quickly become outdated. Ideally, you'd want the documentation about the task logic, including the performed steps, to be generated directly from the source code. Here's how it could look:

![generated docs with task description and step docs](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/bsxcmnfgzg9dy6j2b5lu.png)

We use [Antora](https://antora.org/) to generate internal documentation for our services across different repositories, where code is written in different languages. Antora is a static site generator that allows you to write documentation in AsciiDoc and then generate a website from it. It is very customizable and allows you to combine documentation from different sources, e.g. different repositories into a single, cohesive, versioned documentation site.

In the remainder of this post I want to share how I built a documentation generator that combines GoDoc with application specific logic to generate documentation that can be integrated into an Antora site. On a high level, this will entail:

- Generate Markdown files for each task type, outlining the task logic and steps. I chose Markdown because it is a bit easier to write and more widely supported, but you could generate AsciiDoc directly.
- Convert Markdown to AsciiDoc (skip this step if you decided to generate AsciiDoc directly)
- Integrate the AsciiDoc files into the Antora resources and build the site (skip this step if you don't need a static site) 

## Generating Markdown Documentation

We are going to use [mage](https://magefile.org/) as our build tool. The directory structure of mage-related files looks as follows:

```
.
├── magefile.go
└── mage
    └── docs
        ├── lib.go
        └── task_docs.go
```

Generating the task documentation will be triggered using `mage docs <output-directory>`, thanks to the following function inside `magefile.go`:

```go
// magefile.go
func Docs(outputDir string) error {
	return docs.GenerateDocs(outputDir)
}
```

To implement the `GenerateDocs` function, we'll need to define some types to represent the documentation, i.e.:

- A mechanism to differentiate logic and steps, storing the struct name and package path (`TypeIdent` with `TaskLogicType` and `TaskStepType`)
- `TaskDocs` to store the documentation for a task, including the documentation for the task logic and a list of the steps
- `StepDoc` to store the documentation for a step

We store the `StepDoc` separately, because steps can be reused in multiple tasks. The reference will be done based on the `TaskStepType`. Here's the definition of those types:

```go
// docs/task_docs.go
type TypeIdent struct {
	Name    string
	PkgPath string
}

type TaskLogicType TypeIdent
type TaskStepType TypeIdent

type TaskDocs struct {
	TaskLogicDoc *string
	FileName     string
	StructName   string
	TaskSteps    []TaskStepType
}

type StepDoc struct {
	StructName       string
	FileName         string
	ShortDescription *string
	LongDescription  *string
}
```

Then we'll need to implement the `GenerateDocs` function. This function will extract the task and step documentation from the source code comments, generate the Markdown files, and write them to the output directory.

```go
// docs/lib.go
func GenerateDocs(outputDir string) error {
	taskDocs, stepDocs := ExtractTaskAndStepDocs("./")
	markdownDocs := GenerateMarkdownDocs(taskDocs, stepDocs)
	if len(markdownDocs) == 0 {
		return fmt.Errorf("No task documentation generated. Maybe the generator did not find the source files?")
	}

	err := WriteMarkdownDocsToFiles(markdownDocs, outputDir)
	if err != nil {
		return fmt.Errorf("Error writing task documentation to files: %w", err)
	}
	fmt.Println("Task documentation generated successfully to", outputDir)
	return nil
}
```

Let's dive into `ExtractTaskAndStepDocs` first. Since steps can be reused across tasks, we generate task and step docs separately, merging them later.
The goal of `ExtractTaskAndStepDocs` is to walk through all `.go` files in the project and extract the documentation from the comments.

```go
func ExtractTaskAndStepDocs(rootPrefix string) (map[api.TaskType]TaskDocs, map[TaskStepType]StepDoc) {
	taskLogicLookup, taskStepLookup, taskSteps := buildTaskTypeLookups(controllers.TaskLogics)
	taskDocs := make(map[api.TaskType]TaskDocs)
	stepDocs := make(map[TaskStepType]StepDoc)

	err := filepath.WalkDir(rootPrefix, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if !d.IsDir() && strings.HasSuffix(d.Name(), ".go") {
			processFile(path, taskLogicLookup, taskStepLookup, taskDocs, taskSteps, stepDocs, rootPrefix)
		}

		return nil
	})

	if err != nil {
		log.Fatalf("Error walking through files: %v", err)
	}

	return taskDocs, stepDocs
}
```

The helper function `buildTaskTypeLookups` is listed at the end of the blog post. The core idea is to build lookup maps from the `TaskLogics` that are available in the project. Those lookups will be used when processing the individual files to figure out if the types that are declared in the files are the ones used in the task logic (and thus should be included in the documentation). Let's look at the `processFile` function next.

```go
func processFile(
	filePath string,
	taskLogicLookup map[TaskLogicType]api.TaskType,
	taskStepLookup map[TaskStepType]api.TaskType,
	taskDocs map[api.TaskType]TaskDocs,
	taskSteps map[api.TaskType][]TaskStepType,
	stepDocs map[TaskStepType]StepDoc,
	rootPrefix string,
) {
	fset := token.NewFileSet()

	node, err := parser.ParseFile(fset, filePath, nil, parser.ParseComments)
	if err != nil {
		log.Printf("Failed to parse file %s: %v", filePath, err)
		return
	}

	ast.Inspect(node, func(n ast.Node) bool {
		if genDecl, ok := n.(*ast.GenDecl); ok && genDecl.Tok == token.TYPE {
			processDeclaration(genDecl, filePath, taskLogicLookup, taskStepLookup, taskDocs, taskSteps, stepDocs, rootPrefix)
		}
		return true
	})
}
```

The `processFile` function uses the [Go AST](https://go.dev/ref/spec#Notation) to parse the Go files and extract the documentation from the comments. The `ast.Inspect` function is used to traverse the AST and find all type declarations. We process each declaration in `processDeclaration`.

```go
func processDeclaration(
	genDecl *ast.GenDecl,
	filePath string,
	taskLogicLookup map[TaskLogicType]api.TaskType,
	taskStepLookup map[TaskStepType]api.TaskType,
	allTaskDocs map[api.TaskType]TaskDocs,
	allTaskSteps map[api.TaskType][]TaskStepType,
	stepDocs map[TaskStepType]StepDoc,
	rootPrefix string,
) {
	for _, spec := range genDecl.Specs {
		if typeSpec, ok := spec.(*ast.TypeSpec); ok {
			if _, ok := typeSpec.Type.(*ast.StructType); ok {
				structName := typeSpec.Name.Name
				typeIdent := TypeIdent{structName, filePathToPackagePath(filePath, rootPrefix, packagePrefix)}
				if taskName, exists := taskLogicLookup[TaskLogicType(typeIdent)]; exists {
					processTaskLogic(genDecl, filePath, structName, taskName, allTaskDocs, allTaskSteps[taskName])
				}
				if _, exists := taskStepLookup[TaskStepType(typeIdent)]; exists {
					processTaskStep(genDecl, filePath, structName, stepDocs, rootPrefix)
				}
			}
		}
	}
}
```

The `processDeclaration` function checks if the type is a struct and if it is a task logic or step. If it is a task logic, we process it in `processTaskLogic`. If it is a step, we process it in `processTaskStep`.

```go
func processTaskLogic(genDecl *ast.GenDecl, filePath, structName string, taskName api.TaskType, taskDocs map[api.TaskType]TaskDocs, taskSteps []TaskStepType) {
	taskDocs[taskName] = TaskDocs{
		TaskLogicDoc: extractComment(genDecl),
		FileName:     filePath,
		StructName:   structName,
		TaskSteps:    taskSteps,
	}
}

func processTaskStep(
	genDecl *ast.GenDecl,
	filePath, structName string,
	stepDocs map[TaskStepType]StepDoc,
	rootPrefix string,
) {
	comment := extractComment(genDecl)
	stepDocs[TaskStepType{structName, filePathToPackagePath(filePath, rootPrefix, packagePrefix)}] = StepDoc{
		StructName:       structName,
		FileName:         filePath,
		ShortDescription: extractShortDescription(comment),
		LongDescription:  comment,
	}
}
```

Both functions are rather trivial. They use a few additional helper functions `extractComment`, `extractShortDescription` and `filePathToPackagePath` to extract the documentation from the comments in a structured form. The comments are shown in the detail view of the respective task or step. The short description corresponds to the first sentence of the comment and will be used in the list of steps for a task. The file path is used to link to the source code on GitHub.

```go
func extractComment(genDecl *ast.GenDecl) *string {
	if genDecl.Doc != nil {
		trimmedDoc := strings.TrimSpace(genDecl.Doc.Text())
		return &trimmedDoc
	}
	return nil
}

func extractShortDescription(comment *string) *string {
	if comment == nil {
		return nil
	}
	paragraphs := strings.SplitN(*comment, "\n\n", 2)
	replacedFirstParagraph := strings.ReplaceAll(paragraphs[0], "\n", " ")
	shortDescription := strings.TrimSpace(replacedFirstParagraph)
	return &shortDescription
}

func filePathToPackagePath(filePath, rootPrefix, packagePrefix string) string {
	relativePath := strings.TrimPrefix(filePath, rootPrefix)
	dirPath := filepath.Dir(relativePath)
	packagePath := filepath.Join(packagePrefix, dirPath)
	packagePath = filepath.ToSlash(packagePath)
	return packagePath
}
```

Now that we have the task and step documentation, we can generate the Markdown files in `GenerateMarkdownDocs`. Each task gets its own markdown file.
We could also generate individual files for each step, but I'll leave this exercise to the reader if needed. For the sake of simplicity we'll include the long description of the steps right into the task documentation.

```go
func GenerateMarkdownDocs(taskDocs map[api.TaskType]TaskDocs, stepDocs map[TaskStepType]StepDoc) map[api.TaskType]string {
	markdownDocs := make(map[api.TaskType]string)

	for taskType, docs := range taskDocs {
		var sb strings.Builder

		sb.WriteString(fmt.Sprintf("# %s\n\n", taskType))

		sb.WriteString("## Description\n\n")
		if docs.TaskLogicDoc != nil {
			sb.WriteString(fmt.Sprintf("%s\n", *docs.TaskLogicDoc))
		} else {
			sb.WriteString("No description provided.\n")
		}

		sb.WriteString(fmt.Sprintf("\nYou can find the [source code](%s/%s) on GitHub.\n\n", githubPrefix, docs.FileName))

		sb.WriteString("## Steps\n\n")
		if docs.TaskSteps != nil && len(docs.TaskSteps) > 0 {
			for i, step := range docs.TaskSteps {
				sb.WriteString(fmt.Sprintf("### %d. %s\n\n", i+1, step.Name))
				stepDoc, exists := stepDocs[step]
				if exists && stepDoc.LongDescription != nil {
					sb.WriteString(fmt.Sprintf("%s\n\n", *stepDoc.LongDescription))
				}
			}
		} else {
			sb.WriteString("No steps defined.\n")
		}

		markdownDocs[taskType] = sb.String()
	}

	return markdownDocs
}
```

We are not writing the markdown files directly here, but first building them into a map in order to make the code more testable. The last step will be to write the files for each task to the output directory. This is where `WriteMarkdownDocsToFiles` comes into play.

```go
func WriteMarkdownDocsToFiles(markdownDocs map[api.TaskType]string, outputDir string) error {
	for taskType, content := range markdownDocs {
		fileName := fmt.Sprintf("%s.md", taskType)
		filePath := filepath.Join(outputDir, fileName)

		err := os.WriteFile(filePath, []byte(content), 0644)
		if err != nil {
			return fmt.Errorf("failed to write file %s: %w", filePath, err)
		} else {
			fmt.Printf("Wrote file %s\n", filePath)
		}
	}

	return nil
}
```

That's it on the Go side. Let's look into converting the Markdown files to AsciiDoc and integrating them into the Antora site. If you decided to generate AsciiDoc directly, you can skip this step. If you don't need to add the markdown files to a static site, you can also stop reading now. 

## Convert Markdown to AsciiDoc

To convert Markdown to AsciiDoc we can use `pandoc`. The following script will walk through the markdown files in the provided directory, convert each file to AsciiDoc, and also write a line to the navigation file which will be included as a [partial](https://docs.antora.org/antora/latest/page/include-a-partial/) in the Antora site.

```bash
#!/bin/bash
# integrate_go_docs.sh

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <md_dir> <pages_dir>"
  exit 1
fi

if ! command -v pandoc &> /dev/null
then
  echo "Error: pandoc is not installed. Please install pandoc to continue."
  exit 1
fi

md_dir=$1
pages_dir=$2

tasks_dir="components/operator/tasks"
nav_file="$pages_dir/../partials/task-operator-nav.adoc"

echo "// This file has been generated on $(date)" > "$nav_file"

# Convert task docs
for md_file in "$md_dir"/*.md
do
  adoc_dir="$pages_dir/$tasks_dir"
  adoc_file=$(basename "${md_file%.md}.adoc")
  adoc_path="$adoc_dir/$adoc_file"
  echo "Integrating $md_file"
  # -s to create a standalone document, including the title (=)
  # --shift-heading-level-by -1 to convert the markdown h1 (#) to asciidoc title (=)
  # See https://github.com/jgm/pandoc/issues/5615
  #
  # --wrap=none to avoid wrapping lines, causing long headlines to be broken
  # See https://github.com/jgm/pandoc/issues/3277#issuecomment-264706794
  pandoc -s -f markdown --shift-heading-level-by "-1" --wrap=none -t asciidoc -o "$adoc_path" "$md_file"
  echo "* xref:$tasks_dir/$adoc_file[]" >> "$nav_file"
done
```

With the navigation partial and the individual task AsciiDocs in place, we can build the Antora site. I'm not going to go cover the details of how to use Antora here. Please refer to the [official documentation](https://docs.antora.org/antora/latest/install-and-run-quickstart/) for that.

## Integrate into Antora Site

We're building the site using Antora, which uses the `npm` ecosystem. We'll need scripts to launch `integrate_go_docs.sh` and to run antora with the provided playbook. Here's the `package.json`.

```json
{
  "name": "go-antora-docs",
  "scripts": {
    "generate": "antora --stacktrace --fetch --clean playbooks/generate.yml",
    "go:pandoc": "./integrate_go_docs.sh ../docs/generated ./modules/ROOT/pages"
  },
  "repository": {
    "type": "git",
    "url": "git+https://github.com/yourorg/yourrepo.git"
  },
  "dependencies": {
    "@antora/cli": "^3.1.7",
    "@antora/lunr-extension": "^1.0.0-alpha.8",
    "@antora/site-generator-default": "^3.1.8",
    "@redocly/cli": "^1.25.11",
    "antora": "^3.1.8",
    "http-server": "^14.1.1"
  }
}
```

We are going to use GitHub actions to run the whole pipeline:

```yaml
jobs:
  generate-go-docs:
    runs-on: ubuntu-24.04
    env:
      GOPATH: /home/runner/go
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.24.2'
      - name: Install Mage
        uses: magefile/mage-action@v3
        with:
          install-only: true
          version: "v1.15.0"
      - name: Generate Docs
        run: mage docs docs/generated
      - name: Upload  Docs
        uses: actions/upload-artifact@v4
        with:
          name: go-docs
          path: docs/generated
  compile-docs:
    runs-on: ubuntu-24.04
    needs:
      - go-docs
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 18
      - name: Install Dependencies
        working-directory: site
        run: npm ci
      - name: Install Pandoc
        working-directory: site
        run: |
          sudo apt-get update
          sudo apt-get install -y pandoc
      - name: Download Operator Docs
        uses: actions/download-artifact@v4
        with:
          name: operator-docs
          path: kubernetes/operator/docs/generated
      - name: Generate Operator Pandoc Page
        working-directory: site
        run: npm run "operator:pandoc"
      - name: Generate Antora Page
        working-directory: site
        run: npm run generate
      - name: Copy index HTML
        working-directory: site
        run: cp index.html playbooks/build/site
      - name: Upload antora
        uses: actions/upload-artifact@v4
        with:
          name: antora
          path: site/playbooks/build/site
```

And that's it. The GitHub action will run `mage docs docs/generated`, upload the resulting markdown, then pass it to the next job which downloads it, running `npm run "operator:pandoc"` and then `npm run generate`, finally moving the `index.html` into the build directory and uploading the resulting artifact.

## Conclusion

In this post we've seen how we can generate documentation from Go code and integrate it into an Antora site. The approach can be adapted to other programming languages and documentation formats. The advantage of this approach is that the documentation is easier to keep up-to-date, and it can be enriched with application specific information, tailored towards not only API documentation, but documenting the behaviour of your application.

---

If you liked this post, you can [support me on ko-fi](https://ko-fi.com/frosnerd).

---

```go
func buildTaskTypeLookups(original map[api.TaskType]task.TaskLogic) (map[TaskLogicType]api.TaskType, map[TaskStepType]api.TaskType, map[api.TaskType][]TaskStepType) {
	invertedLogics := make(map[TaskLogicType]api.TaskType)
	invertedSteps := make(map[TaskStepType]api.TaskType)
	steps := make(map[api.TaskType][]TaskStepType)

	for apiName, logic := range original {
		logicType := reflect.TypeOf(logic)
		invertedLogics[TaskLogicType{logicType.Name(), logicType.PkgPath()}] = apiName

		logicSteps := logic.GetSteps()
		for _, step := range logicSteps {
			stepType := reflect.TypeOf(step)
			stepTypeSpec := TaskStepType{stepType.Name(), stepType.PkgPath()}
			invertedSteps[stepTypeSpec] = apiName
			steps[apiName] = append(steps[apiName], stepTypeSpec)
		}
	}

	return invertedLogics, invertedSteps, steps
}
```
