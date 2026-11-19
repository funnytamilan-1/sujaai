import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
const apiBase = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000/api');
const googleServerClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');
void main() => runApp(const SujaaiApp());
class SujaaiApp extends StatelessWidget {
 const SujaaiApp({super.key});
 @override Widget build(BuildContext context)=>MaterialApp(title:'SUJAAI',debugShowCheckedModeBanner:false,theme:ThemeData(colorScheme:ColorScheme.fromSeed(seedColor:const Color(0xff087d59)),useMaterial3:true),home:const SessionGate());
}
class SessionGate extends StatefulWidget { const SessionGate({super.key}); @override State<SessionGate> createState()=>_SessionGateState(); }
class _SessionGateState extends State<SessionGate>{
 String? token;
 @override void initState(){super.initState();_restore();}
 Future<void> _restore() async {final p=await SharedPreferences.getInstance();if(mounted)setState(()=>token=p.getString('sujaai_token'));}
 Future<void> _signedIn(String v) async {final p=await SharedPreferences.getInstance();await p.setString('sujaai_token',v);if(mounted)setState(()=>token=v);}
 Future<void> _signOut() async {await GoogleSignIn().signOut();final p=await SharedPreferences.getInstance();await p.remove('sujaai_token');if(mounted)setState(()=>token=null);}
 @override Widget build(BuildContext c)=>token==null?LoginPage(onSignedIn:_signedIn):WorkspacePage(token:token!,onSignOut:_signOut);
}
class LoginPage extends StatefulWidget {final ValueChanged<String> onSignedIn;const LoginPage({super.key,required this.onSignedIn});@override State<LoginPage> createState()=>_LoginPageState();}
class _LoginPageState extends State<LoginPage>{
 bool busy=false;String error='';
 Future<void> _login() async {
  setState(()=>{busy=true,error=''});
  try{
   final g=GoogleSignIn(scopes:const ['email'],serverClientId:googleServerClientId.isEmpty?null:googleServerClientId);
   final account=await g.signIn();if(account==null)return;
   final auth=await account.authentication;final idToken=auth.idToken;
   if(idToken==null)throw Exception('Google did not return an ID token. Check OAuth configuration.');
   final r=await http.post(Uri.parse('$apiBase/auth/google'),headers:{'Content-Type':'application/json'},body:jsonEncode({'credential':idToken}));
   final data=jsonDecode(r.body);if(r.statusCode<200||r.statusCode>=300)throw Exception(data['detail']??'Google login failed');
   widget.onSignedIn(data['access_token'] as String);
  }catch(e){if(mounted)setState(()=>error=e.toString().replaceFirst('Exception: ',''));}
  finally{if(mounted)setState(()=>busy=false);}
 }
 @override Widget build(BuildContext c)=>Scaffold(body:Center(child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:420),child:Padding(padding:const EdgeInsets.all(28),child:Column(mainAxisSize:MainAxisSize.min,children:[
  const CircleAvatar(radius:34,child:Text('S',style:TextStyle(fontSize:30,fontWeight:FontWeight.bold))),
  const SizedBox(height:20),const Text('SUJAAI',style:TextStyle(fontSize:27,fontWeight:FontWeight.bold)),
  const Text('Your business workspace',style:TextStyle(color:Colors.black54)),const SizedBox(height:24),
  if(error.isNotEmpty)Text(error,style:const TextStyle(color:Colors.red)),
  FilledButton.icon(onPressed:busy?null:_login,icon:const Icon(Icons.login),label:Text(busy?'Signing in…':'Continue with Google')),
  const SizedBox(height:12),const Text('Access is limited to the configured workspace administrator.',textAlign:TextAlign.center,style:TextStyle(fontSize:12,color:Colors.black54))
])))));
}
class WorkspacePage extends StatefulWidget {final String token;final VoidCallback onSignOut;const WorkspacePage({super.key,required this.token,required this.onSignOut});@override State<WorkspacePage> createState()=>_WorkspacePageState();}
class _WorkspacePageState extends State<WorkspacePage>{
 List<dynamic> records=[];bool busy=false;String error='';
 Future<void> _load() async {
  setState(()=>{busy=true,error=''});
  try{final r=await http.get(Uri.parse('$apiBase/workspace/records'),headers:{'Authorization':'Bearer '+widget.token});
   if(r.statusCode!=200)throw Exception(jsonDecode(r.body)['detail']??'Could not load records');
   setState(()=>records=jsonDecode(r.body) as List<dynamic>);
  }catch(e){setState(()=>error=e.toString());}finally{if(mounted)setState(()=>busy=false);}
 }
 @override void initState(){super.initState();_load();}
 Future<void> _addCustomer() async {
  final name=TextEditingController(),phone=TextEditingController();
  final ok=await showDialog<bool>(context:context,builder:(c)=>AlertDialog(title:const Text('New customer'),content:Column(mainAxisSize:MainAxisSize.min,children:[
   TextField(controller:name,decoration:const InputDecoration(labelText:'Customer name')),
   TextField(controller:phone,keyboardType:TextInputType.phone,decoration:const InputDecoration(labelText:'Mobile number'))
  ]),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:const Text('Cancel')),FilledButton(onPressed:()=>Navigator.pop(c,true),child:const Text('Save'))]));
  if(ok!=true||name.text.trim().isEmpty)return;
  final r=await http.post(Uri.parse('$apiBase/workspace/records'),headers:{'Authorization':'Bearer '+widget.token,'Content-Type':'application/json'},body:jsonEncode({'type':'customer','title':name.text.trim(),'data':{'name':name.text.trim(),'phone':phone.text.trim()}}));
  if(r.statusCode<200||r.statusCode>=300){setState(()=>error=jsonDecode(r.body)['detail']??'Save failed');}else{_load();}
 }
 @override Widget build(BuildContext c)=>Scaffold(appBar:AppBar(title:const Text('SUJAAI Workspace'),actions:[IconButton(onPressed:_load,icon:const Icon(Icons.refresh)),IconButton(onPressed:widget.onSignOut,icon:const Icon(Icons.logout))]),
  floatingActionButton:FloatingActionButton.extended(onPressed:_addCustomer,icon:const Icon(Icons.person_add),label:const Text('Customer')),
  body:RefreshIndicator(onRefresh:_load,child:ListView(padding:const EdgeInsets.all(16),children:[
   Card(child:Padding(padding:const EdgeInsets.all(18),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('Business records',style:TextStyle(fontSize:18,fontWeight:FontWeight.bold)),Text(records.length.toString()+' saved records'),if(busy)const LinearProgressIndicator()]))),
   if(error.isNotEmpty)Padding(padding:const EdgeInsets.all(8),child:Text(error,style:const TextStyle(color:Colors.red))),
   ...records.map((item)=>Card(child:ListTile(leading:const CircleAvatar(child:Icon(Icons.folder_open)),title:Text(item['title']?.toString()??'Record'),subtitle:Text(item['type']?.toString()??'')))),
   if(records.isEmpty&&!busy)const Padding(padding:EdgeInsets.all(24),child:Text('No records yet. Add your first customer.',textAlign:TextAlign.center))
  ])));
}
