:orphan:
.. currentmodule:: discord

.. _guide_topic_embeds:


Embeds
=======

Embeds are special message that are formatted to embed rich content within. You may have ever sent a link to a server and
seen one appear with a brief description and maybe an image or video.

.. |link_embed_google| image:: /images/guide/topics/embeds/link_embed_google.png
   :scale: 38%
   :target: https://google.com/search?q=discord%20inc
.. |link_embed_discord| image:: /images/guide/topics/embeds/link_embed_discord.png
   :scale: 38%
   :target: https://discord.com
.. |link_embed_youtube| image:: /images/guide/topics/embeds/link_embed_youtube.png
   :scale: 38%
   :target: https://www.youtube.com/watch?v=TJ13BA3-NR4&
.. |link_embed_github| image:: /images/guide/topics/embeds/link_embed_github.png
   :scale: 38%
   :target: https://github.com/Rapptz/discord.py

+---------------------+----------------------+----------------------+---------------------+
| |link_embed_google| | |link_embed_discord| | |link_embed_youtube| | |link_embed_github| |
+---------------------+----------------------+----------------------+---------------------+

The examples above are just a few common samples of what you seen often around Discord, these are automatically generated 
by discord based on the metadata from the linked sites but you don't need to remember any of this.

Internally, an embed is represented with a JSON payload by the API. discord.py offers a 
builder-esque interface over this payload to help make the process more straightforward and intuitive in Python.

Let's take a look at a basic example of using the builder:

.. code-block:: python

    import discord

    embed = discord.Embed(
        title = "Hello World",
        description = "This is a description",
        colour = discord.Colour.blurple()
    )

And then we can send it to a channel using the ``embed`` keyword-only argument:

.. code-block:: python

    await channel.send(embed=embed)

On Discord, this will look like:

.. image:: /images/guide/topics/embeds/basic_embed.png
    :scale: 50%

Let's break down what we did.

First, we imported the ``discord`` module. This is required to access the ``Embed`` class.

Next, we created an instance of the ``Embed`` class. This is the object that will contain the basic fields of our embed.

The ``title`` and ``description`` fields are pretty self-explanatory. The ``colour`` field is a bit more interesting.
This field is used to set the colour of the left-hand side of the embed. We used the :meth:`discord.Colour.blurple()` classmethod on the 
:class:`discord.Colour` class that discord.py provides to get the blurple colour. It can also be set to an integer
representing a hexadecimal colour code like ``0x5865f2`` or ``5793266``.


Instead of passing fields directly to ``Embed``, you can also set basic fields after construction, like so:  

.. code-block:: python  

    embed = discord.Embed()  
    embed.title = "Hello World"  
    embed.description = "This is a description"  
    embed.colour = discord.Colour.blurple()  

.. tip::  
    
    US English spellings can use the respective ``color`` and ``Color`` aliases instead.  

.. note::
    There are two other basic fields that we didn't show here, ``url`` and ``timestamp``. The ``url`` field is used to set the
    URL that the title of the embed should be masked with. The ``timestamp`` field is used to set the timestamp of the embed. This
    field takes a :class:`datetime.datetime` timezone-aware object, such as from :func:`utils.utcnow`.

    Try adding these two fields to the embed the same way we did with the other fields and see what happens.

Finally, we sent the embed to a channel. We used the ``embed`` keyword-only argument to do this. This argument takes an 
instance of the ``Embed`` class which we created earlier and assigned to the ``embed`` variable.

Fields
-------

Fields can be used to add subsections to an embed, each one contains two articles of information; a name and a value.

Starting off with a few basic fields.

Since embed fields need both a name and value, a field is added by calling :meth:`embed.add_field()<Embed.add_field>`:

.. code-block:: python

    embed = discord.Embed(
        title = "Weather in San Francisco, CA",
        description = "Sunny with a High of 55F and a Low of 49F\nFeels like: 55F",
        colour = discord.Colour.yellow()
    )

    embed.add_field(name="Precipitation", value="0%", inline=False)
    embed.add_field(name="Wind", value="5 mph", inline=True)
    embed.add_field(name="Humidity", value="96%")

    await channel.send(embed=embed)	

Let's see it on Discord:

.. image:: /images/guide/topics/embeds/fields_embed.png
    :scale: 50%


Notice how how the fields are in a certain order, the ``Precipitation`` field is on the top and the other two are next to
each other on the bottom. This is because of the ``inline`` argument. This argument takes either ``True`` or ``False`` to 
determine whether or not the field should be on its own block. This is why the ``Precipitation`` field is on the top. 
If the argument is not passed, it's always ``True``.


Let's see what happens when we add a fourth field and don't pass the ``inline`` argument:

.. code-block:: python

    embed = discord.Embed(
        title = "Weather in San Francisco, CA",
        description = "Sunny with a High of 55F and a Low of 49F\nFeels like: 55F",
        colour = discord.Colour.yellow()
    )

    embed.add_field(name="Precipitation", value="0%", inline=False)
    embed.add_field(name="Wind", value="5 mph", inline=True)
    embed.add_field(name="Humidity", value="96%")
    embed.add_field(
        name="Fact about this location",
        value="Golden Gate Park outstrips Central Park"
    )

    await channel.send(embed=embed)

.. image:: /images/guide/topics/embeds/fields_embed_inline.png

As you can see, the ``Fact about this location`` field was added next to the ``Humidity`` field. This is because we didn't 
specify the ``ìnline`` argument. If you want to force a field to be on its own row, you can pass ``inline=False`` to 
the ``add_field`` method. 

Each row of fields can only contain a maximum of 3 fields, depending on the user's display size.

.. note::

    Fields should be displayed in the order they were added, but if you want to change the order, you can use 
    the :meth:`embed.insert_field_at()<Embed.insert_field_at>` method to insert a field at a specific index or
    :meth:`embed.set_field_at()<Embed.set_field_at>` to replace a field at a specific index.

    Try using these methods to change the order of the fields in the embed.
    
    Remember that the index of the first field is 0, the second field is 1, and so on.

Author & Footer
----------------

Let's quickly glance over the ``author`` and ``footer`` fields.

The ``author`` field is a the top of the embed containing:

- A name (``name=`` argument, required)
- An icon URL (``icon_url=`` argument, optional)
- A hyperlinked URL, masked by the name (``url=`` argument, optional)

The ``footer`` field is at the bottom of the embed containing:

- A text (``text=`` argument, required)
- An icon URL (``icon_url=`` argument, optional)

All arguments are keyword-only.

Let's see an example of both:

.. code-block:: python

    embed = discord.Embed(
        title = "Weather in San Francisco, CA",
        description = "Sunny with a High of 55F and a Low of 49F\nFeels like: 55F",
        colour = discord.Colour.yellow()
    )

    embed.add_field(name="Precipitation", value="0%", inline=False)
    embed.add_field(name="Wind", value="5 mph", inline=True)
    embed.add_field(name="Humidity", value="96%")
    embed.add_field(
        name="Fact about this location",
        value="Golden Gate Park outstrips Central Park"
    )

    embed.set_author(name=bot.user.name, icon_url=bot.user.display_avatar.url)
    embed.set_footer(
        text="Powered by OpenWeatherMap",
        icon_url="https://openweathermap.org/themes/openweathermap/assets/vendor/owm/img/icons/logo_32x32.png"
    )

    await channel.send(embed=embed)

.. image:: /images/guide/topics/embeds/author_footer_embed.png
    :scale: 50%

A breakdown of what we did, we set the ``author`` field to the bot's name and avatar URL and the ``footer``'s text to 
"Powered by OpenWeatherMap" and ``icon_url`` to OpenWeatherMap's logo.

Images
-------

There are two ways to add images to an embed:

- As the embed's ``image``.
- As the embed's ``thumbnail``.

At the time of writing, bots cannot embed videos.

We will add an `image of the Golden Gate Bridge`_ to the embed by calling :meth:`embed.set_image() <Embed.set_image>`:

.. code-block:: python

    image_url = "https://upload.wikimedia.org/wikipedia/commons/0/0c/GoldenGateBridge-001.jpg"
    embed.set_image(url=image_url)

.. _image of the Golden Gate Bridge: https://commons.wikimedia.org/wiki/Golden_Gate_Bridge#/media/File:GoldenGateBridge-001.jpg

.. image:: /images/guide/topics/embeds/image_embed.png
    :scale: 70%

As seen above, when setting :attr:`Embed.image`, the provided URL will be displayed at the bottom of the embed.

The alternative to this, is to set :attr:`Embed.thumbnail`, which would be displayed in the top right corner of the embed.

Files
------

You may have noticed that we used URLs to for each of the images in the embeds above but what if we wanted to use a local file? 
That's possible too, we can use the :class:`File` class and set the url fields to a special URI scheme that Discord provides - ``attachment://``.

Let's set the thumbnail of the weather embed to a local file.

First, we have to construct a :class:`File` object. The first argument is the file path, and the second is the name of the attachment that will be used to refer to it within Discord.

.. code-block:: python

    file = discord.File('./images/sunny_weather.png', 'thumbnail.png')

.. warning::

    The filename for these URLs must be ASCII alphanumeric with underscores, dashes, or dots. This is a Discord limitation.

Next, we need to call :meth:`embed.set_thumbnail() <Embed.set_thumbnail>` to set the thumbnail.
To refer to our attachment for the thumbnail, we will use a special URI scheme as discussed above.

Since we called our file ``thumbnail.png``, we will set the ``url`` parameter to ``attachment://thumbnail.png``.

.. code-block:: python

    embed.set_thumbnail(url="attachment://thumbnail.png")

And finally, we will send the embed with the ``file`` parameter set to our file.

.. code-block:: python

    await channel.send(file=file, embed=embed)

It should look the same as before but now we are using a local file instead of a URL.

More about this can be found at :ref:`local_image`


Reading values off an embed
----------------------------

Now that we have constructed our embed, let's see how we can get the values from it if for example we get it from a :class:`Message`.

Let's start by getting the title of the embed.

We can do this by using the :attr:`Embed.title` attribute.

.. code-block:: python

    >>> print(embed.title)
    'Weather in San Francisco, CA'

That was easy!

Now, let's get the footer text.

.. code-block:: python

    >>> print(embed.footer.text)
    'Powered by OpenWeatherMap'

But what if we remove the footer and try again?

.. code-block:: python

    >>> embed.remove_footer()
    >>> print(embed.footer.text)
    None

As you can see, it returns ``None``, this is because attribute like ``author`` and ``footer`` return a special object that returns ``None`` when the attribute is not set.

This is the same for all other attributes that got more than one value like :attr:`Embed.fields`, :attr:`Embed.image`, etc.

Most of these attributes have more attributes compared to what we can set, for example, the :attr:`Embed.image` attributes called ``width`` and 
``height`` that return the width and height of the image respectively.

.. code-block:: python

    >>> print(embed.image.width)
    1024 # or None
    >>> print(embed.image.height)
    768 # or None

Other attributes can be found in the :class:`Embed` documentation for the reprecive attribute.

Proxy URLs
~~~~~~~~~~~

This is a cached version of the url in the case of images. When the message is deleted, this URL might be valid for a few minutes or not valid at all.

The following field can have a proxy URL:

- :attr:`Embed.image`
- :attr:`Embed.thumbnail`
- :attr:`Embed.author`
- :attr:`Embed.footer`

.. code-block:: python

    >>> print(embed.thumbnail.proxy_url)
    'https://media.discordapp.net/attachments/123456789012345678/8765432187654321/image.png'


Other Methods
-------------

There are a few other methods that may be useful when working with embeds.

.. method:: Embed.from_dict()
    :noindex:
    
    Creates an embed from a Python dictionary.

    .. code-block:: python

        payload = {
            "title": "Hello, World!",
            "description": "This bot is running on discord.py!",
            "color": 0x00FF00
        }
        embed = discord.Embed.from_dict(payload)

    .. warning::
        
        Each key needs to match the structure of an embed from Discord's API.
        Namely, the API doesn't alias `colour` and `color` needs to be used instead.
        :ddocs:`Embeds as documented by Discord<resources/channel#embed-object>`.
        

.. method:: Embed.to_dict()
    :noindex:

    Inversely, `to_dict` converts the embed to a dictionary compatible with the API's embed specification.

    .. code-block:: python

        >>> embed.to_dict()
        {'title': 'Hello, World!', 'description': 'This bot is running on discord.py!', 'type': 'rich', 'color': 65280}

Other can be found in the :class:`Embed` documentation.


Restrictions and limits
------------------------

There are a few restrictions and limits that you should be aware of when working with embeds.

Markdown support
~~~~~~~~~~~~~~~~~

Markdown like **this**, *that*, and even ``this`` is supported in embeds, but only in certain fields.

More about this can be found at :ref:`_guide_topic_markdown`.

All strings
~~~~~~~~~~~~

All values passed to the embed must be a string.

Except for ``timestamp`` and ``colour`` which must be a :class:`datetime.datetime` and :class:`Colour` / ``int``, respectively.

discord.py attempts to convert all values given to string using ``str()``.
This can be confusing for beginning users of Python as they may not be aware of this, most objects have a ``__str__`` method that 
returns a string representation of the object. Most objects in discord.py also do this, like :class:`Asset`, that is returned from
attributes like :attr:`User.avatar` and :attr:`Guild.icon`, calling ``str()`` on any of those returns the URL of the asset.
That is precisely why you can pass these attributes to the ``url`` or ``icon_url`` parameter of the methods or :attr:`User` to ``name`` in
:meth:`embed.set_author() <Embed.set_author>`. It will work but it's not encouraged to do so.

Try it out:

.. code-block:: python

    embed.set_author(name=bot.user, icon_url=bot.user.display_avatar)

Character limits
~~~~~~~~~~~~~~~~~

Each field has its own character limit. Unfortunately, listing all the limits here would quickly become 
outdated, but you can find them in the :ddocs:`Discord API documentation<resources/channel#embed-object>`.