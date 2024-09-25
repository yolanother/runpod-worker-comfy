#!/bin/bash

# Prepare hooks directory
mkdir -p .git/hooks

# Pre-commit hook: Updates the version in version.txt
cat << 'EOF' > .git/hooks/pre-commit
#!/bin/bash

# Path to version.txt
VERSION_FILE="version.txt"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: version.txt not found!"
    exit 1
fi

# Read the current version
VERSION=$(cat "$VERSION_FILE")
echo "Current version: $VERSION"

# Increment the patch version (x.x.PATCH)
NEW_VERSION=$(echo "$VERSION" | awk -F. '{$NF = $NF + 1;} 1' | sed 's/ /./g')
echo "New version: $NEW_VERSION"

# Update the version in version.txt
echo "$NEW_VERSION" > "$VERSION_FILE"

# Stage the updated version.txt
git add "$VERSION_FILE"

echo "Updated version.txt to $NEW_VERSION"
EOF

# Make the pre-commit hook executable
chmod +x .git/hooks/pre-commit

# Post-commit hook: Tags the commit with the updated version in the format dev-<version> and pushes the tag to the remote
cat << 'EOF' > .git/hooks/post-commit
#!/bin/bash

# Path to version.txt
VERSION_FILE="version.txt"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: version.txt not found!"
    exit 1
fi

# Read the version
VERSION=$(cat "$VERSION_FILE")

# Create a tag in the format dev-<version>
TAG="dev-$VERSION"

# Tag the commit with the new tag
git tag "$TAG"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create the tag"
    exit 1
fi

echo "Tagged the commit with version: $TAG"

# Push the commit and the tag to the remote repository
git push origin
git push origin --tags

if [ $? -ne 0 ]; then
    echo "Error: Failed to push the tag"
    exit 1
fi

echo "Pushed commit and tag to remote."
EOF

# Make the post-commit hook executable
chmod +x .git/hooks/post-commit

echo "Git hooks installed successfully!"
