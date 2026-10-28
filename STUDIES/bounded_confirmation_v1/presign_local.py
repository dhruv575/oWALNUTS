"""Fallback URL signer using the existing local AWS login; never prints secrets."""
import argparse,json,sys
from pathlib import Path
import boto3

def main():
    parser=argparse.ArgumentParser();parser.add_argument('metadata');parser.add_argument('output');parser.add_argument('--version');args=parser.parse_args()
    try:
        spec=json.loads(Path(args.metadata).read_text());out=Path(args.output)
        if out.exists():raise FileExistsError('Inspect existing secret')
        if spec['bucket']!='owalnuts-research-712710405275-us-east-2':raise ValueError('Research bucket only')
        if not spec['key'].startswith('evidence/sha256/'+spec['sha256']+'/'):raise ValueError('Content-addressed key required')
        session=boto3.Session(profile_name='owalnuts',region_name='us-east-2')
        if session.client('sts').get_caller_identity()['Account']!='712710405275':raise ValueError('Research account mismatch')
        client=session.client('s3');params=dict(Bucket=spec['bucket'],Key=spec['key'])
        if args.version:params['VersionId']=args.version;operation='get_object';spec['version_id']=args.version
        else:params['ServerSideEncryption']='AES256';operation='put_object'
        spec['url']=client.generate_presigned_url(operation,Params=params,ExpiresIn=900)
        with out.open('x') as f:json.dump(spec,f)
        print(json.dumps(dict(status='signed',operation=operation,expires_seconds=900)))
        return 0
    except Exception as e:
        print(json.dumps(dict(status='failed',error_type=type(e).__name__)));return 1

if __name__=='__main__':sys.exit(main())
