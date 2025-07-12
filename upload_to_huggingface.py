"""
Upload a folder to Hugging Face Model Repository (just ignore this file)
"""

import sys
from pathlib import Path
from huggingface_hub import HfApi, create_repo, upload_folder, upload_large_folder
import argparse


class HuggingFaceUploader:
    def __init__(self, token: str):
        """
        Initialize the uploader with HF token
        
        Args:
            token: Hugging Face authentication token
        """
        self.api = HfApi(token=token)
        self.token = token
    
    def create_model_repo(self, repo_name: str, private: bool = False, exist_ok: bool = True):
        """
        Create a new model repository on Hugging Face
        
        Args:
            repo_name: Name of the repository (format: username/repo-name)
            private: Whether the repository should be private
            exist_ok: If True, do not raise an error if repo already exists
        
        Returns:
            Repository URL
        """
        try:
            repo_url = create_repo(
                repo_id=repo_name,
                token=self.token,
                repo_type="model",
                private=private,
                exist_ok=exist_ok
            )
            print(f"Repository created/verified: {repo_url}")
            return repo_url
        except Exception as e:
            print(f"Error creating repository: {e}")
            raise
    
    def upload_folder_to_repo(self, 
                             folder_path: str, 
                             repo_name: str, 
                             path_in_repo: str = None,
                             commit_message: str = None):
        """
        Upload a folder to the Hugging Face repository
        
        Args:
            folder_path: Local path to the folder to upload
            repo_name: Name of the repository (format: username/repo-name)
            path_in_repo: Path within the repository (None for root)
            commit_message: Commit message for the upload
        
        Returns:
            Commit info
        """
        folder_path = Path(folder_path)
        
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        if commit_message is None:
            commit_message = f"Upload {folder_path.name} folder"
        
        try:
            print(f"Uploading folder: {folder_path}")
            print(f"To repository: {repo_name}")
            print(f"Commit message: {commit_message}")
            
            commit_info = upload_folder(
                folder_path=str(folder_path),
                repo_id=repo_name,
                repo_type="model",
                path_in_repo=path_in_repo,
                commit_message=commit_message,
                token=self.token
            )
            
            print(f"Upload completed successfully!")
            print(f"Commit: {commit_info.oid}")
            return commit_info
            
        except Exception as e:
            print(f"Error uploading folder: {e}")
            raise

    def upload_large_folder_to_repo(self, 
                             folder_path: str, 
                             repo_name: str, 
                             path_in_repo: str = None,
                             commit_message: str = None):
        """
        Upload large folder to the Hugging Face repository
        
        Args:
            folder_path: Local path to the folder to upload
            repo_name: Name of the repository (format: username/repo-name)
        
        Returns:
            Commit info
        """
        folder_path = Path(folder_path)
        
        if not folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")
        
        try:
            print(f"Uploading folder: {folder_path}")
            print(f"To repository: {repo_name}")
            
            commit_info = upload_large_folder(
                folder_path=str(folder_path),
                repo_id=repo_name,
                repo_type="model",
            )
            
            print(f"Upload completed successfully!")
            return commit_info
            
        except Exception as e:
            print(f"Error uploading folder: {e}")
            raise
    
    def upload_single_file(self, 
                          file_path: str, 
                          repo_name: str, 
                          path_in_repo: str = None,
                          commit_message: str = None):
        """
        Upload a single file to the repository
        
        Args:
            file_path: Local path to the file
            repo_name: Name of the repository
            path_in_repo: Path within the repository (None to use same filename)
            commit_message: Commit message
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if path_in_repo is None:
            path_in_repo = file_path.name
        
        if commit_message is None:
            commit_message = f"Upload {file_path.name}"
        
        try:
            print(f"Uploading file: {file_path}")
            
            commit_info = self.api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=path_in_repo,
                repo_id=repo_name,
                repo_type="model",
                commit_message=commit_message
            )
            
            print(f"File uploaded successfully!")
            return commit_info
            
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise
    
    def list_repo_files(self, repo_name: str):
        """
        List files in the repository
        
        Args:
            repo_name: Name of the repository
        """
        try:
            files = self.api.list_repo_files(repo_id=repo_name, repo_type="model")
            print(f"Files in {repo_name}:")
            for file in files:
                print(f"  - {file}")
            return files
        except Exception as e:
            print(f"Error listing files: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Upload folder to Hugging Face Model Repository")
    parser.add_argument("--token", required=True, help="Hugging Face token")
    parser.add_argument("--repo-name", required=True, help="Repository name (username/repo-name)")
    parser.add_argument("--folder-path", required=True, help="Path to folder to upload")
    parser.add_argument("--path-in-repo", help="Path within repository (optional)")
    parser.add_argument("--private", action="store_true", help="Create private repository")
    parser.add_argument("--commit-message", help="Custom commit message")
    parser.add_argument("--create-repo", action="store_true", help="Create repository if it doesn't exist")
    
    args = parser.parse_args()
    
    try:
        # Initialize uploader
        uploader = HuggingFaceUploader(args.token)
        
        # Create repository if requested
        if args.create_repo:
            uploader.create_model_repo(args.repo_name, private=args.private)
        
        # Upload folder
        uploader.upload_folder_to_repo(
            folder_path=args.folder_path,
            repo_name=args.repo_name,
            path_in_repo=args.path_in_repo,
            commit_message=args.commit_message
        )
        
        # List files after upload
        uploader.list_repo_files(args.repo_name)
        
    except Exception as e:
        print(f"Script failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
