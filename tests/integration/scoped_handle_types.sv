class Item;int value;function new(int value=0);this.value=value;endfunction endclass
typedef Item Items[$];
typedef Items Groups[string];
class Owner;
Item item;
Items items;
Groups groups;
function new(Item value);item=value;endfunction
static function Item make(int value);Item result=new(value);return result;endfunction
virtual function Item echo(Item value);return value;endfunction
function Items echo_many(Items values);return values;endfunction
function Groups echo_groups(Groups values);return values;endfunction
function int read(Item value);return value==null?-1:value.value;endfunction
task exchange(input Item value,output Item previous,inout Item changed);
#1ns;previous=item;item=value;changed=value;
endtask
endclass
class Consumer;
static function int read(Item value);return value==null?-1:value.value;endfunction
static function Item echo(Item value);return value;endfunction
endclass
