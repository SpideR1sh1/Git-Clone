
# Making My Own Git

This project is a minimal implementation of Git, developed in Python, that replicates core functionalities of the distributed version control system. It serves as a learning tool to understand how Git works under the hood, including how it stores and manipulates data.

---

## **Features**

1. **Repository Management**:
   - Create and initialize Git repositories.
   - Manage `.git` directories with essential metadata and configurations.

2. **Object Storage**:
   - Implement object storage using SHA-1 hashing for blobs, trees, and commits.
   - Store and retrieve objects in Git's compressed format.

3. **Basic Git Operations**:
   - `init`: Create a new repository.
   - `add`: Stage changes by adding files to the index.
   - `commit`: Record staged changes in a commit object.
   - `log`: View commit history.
   - `cat-file`: Inspect Git objects (e.g., blobs, commits).

4. **Branching**:
   - Create and switch between branches.
   - Manage references for branch heads.

5. **Learning Tool**:
   - Provides detailed insights into Git’s internal structure and concepts like blobs, trees, commits, and refs.

---

## **Installation**

### **Prerequisites**
- Python (version 3.7 or later)

### **Setup**
1. Clone this repository:
   ```bash
   git clone https://github.com/SpideR1sh1/Git-Clone.git
   cd wyag
   ```

2. Run the script directly:
   ```bash
   python wyag.py
   ```

---

## **Implemented Commands**

### Repository Management
- `wyag init`: Initialize a new Git repository.
  ```bash
  python wyag.py init
  ```

### Object Management
- `wyag hash-object`: Create a blob object and store it.
  ```bash
  echo "Hello, WYAG!" | python wyag.py hash-object -w
  ```

- `wyag cat-file`: Inspect objects in the repository.
  ```bash
  python wyag.py cat-file blob <SHA-1>
  ```

### Staging and Committing
- `wyag add`: Add files to the staging area.
  ```bash
  python wyag.py add <filename>
  ```

- `wyag commit`: Create a new commit.
  ```bash
  python wyag.py commit -m "Initial commit"
  ```

### Viewing History
- `wyag log`: View the commit history.
  ```bash
  python wyag.py log
  ```

### Branching
- `wyag branch`: Create or list branches.
  ```bash
  python wyag.py branch <branch_name>
  ```

- `wyag checkout`: Switch to a branch.
  ```bash
  python wyag.py checkout <branch_name>
  ```

---

## **Project Structure**

```
.
├── wyag.py        # Main script implementing Git functionality
├── objects.py     # Handles Git objects (blobs, trees, commits)
├── repository.py  # Manages repository initialization and configuration
├── utils.py       # Utility functions for file I/O and hashing
└── README.md      # Documentation
```

---

## **How It Works**

### 1. **Repository Structure**
- Initializes a `.git` directory containing objects, refs, and configuration files.

### 2. **Object Storage**
- Objects (blobs, trees, commits) are hashed using SHA-1 and stored in a compressed format in `.git/objects/`.

### 3. **Indexing and Committing**
- Stages changes by creating a temporary index file.
- Commits reference staged changes and previous commits.

### 4. **Branch Management**
- Branches are managed using references in `.git/refs/heads/`.

---

## **Learning Objectives**
- Understand Git’s internal workings: object storage, indexing, and branching.
- Explore the data structures (blobs, trees, commits) that form the backbone of Git.
- Learn how Git efficiently tracks changes and manages history.

---

## **Usage Examples**

### Initialize a Repository
```bash
python wyag.py init
```

### Add and Commit Files
```bash
echo "Hello, WYAG!" > file.txt
python wyag.py add file.txt
python wyag.py commit -m "Added file.txt"
```

### View Commit History
```bash
python wyag.py log
```

### Inspect an Object
```bash
python wyag.py cat-file blob <SHA-1>
```

---

## **Planned Features**
- Add support for merging branches.
- Implement `diff` to view changes between commits.
- Extend `log` to show graphical commit trees.

---

### **Acknowledgments**
- Sincere thanks to **Thibault Polge**, whose *“Write Yourself a Git”* tutorial served as an invaluable learning resource and foundation for this implementation.

---

## **License**
This project is licensed under the MIT License.
